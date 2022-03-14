import numpy as np
import copy
import pathlib

from ipywidgets import *
from tomopyui._sharedvars import *
from abc import ABC, abstractmethod
from tomopyui.widgets.view import (
    BqImViewer_Import_Analysis,
    BqImViewer_Altered_Analysis,
    BqImViewer_DataExplorer_AfterAnalysis,
)
from tomopyui.backend.align import TomoAlign
from tomopyui.backend.recon import TomoRecon
from tomopyui.backend.io import (
    Projections_Prenormalized,
    Metadata_Align,
    Metadata_Recon,
)


class AnalysisBase(ABC):
    def init_attributes(self, Import, Center):

        self.Import = Import
        self.Center = Center
        self.projections = copy.deepcopy(Import.projections)
        self.imported_viewer = BqImViewer_Import_Analysis(self)
        self.imported_viewer.create_app()
        self.altered_viewer = BqImViewer_Altered_Analysis(self.imported_viewer, self)
        self.altered_viewer.create_app()
        self.result_before_viewer = self.altered_viewer
        self.result_after_viewer = BqImViewer_DataExplorer_AfterAnalysis(
            self.result_before_viewer
        )
        self.wd = None
        self.log_handler, self.log = Import.log_handler, Import.log
        self.downsample = False
        self.downsample_factor = 0.5
        self.num_iter = 1
        self.center = Center.current_center
        self.upsample_factor = 50
        self.extra_options = {}
        self.num_batches = 20
        self.pixel_range_x = (0, 10)
        self.pixel_range_y = (0, 10)
        self.paddingX = 10
        self.paddingY = 10
        self.use_subset_correlation = False
        self.pre_alignment_iters = 1
        self.tomopy_methods_list = [key for key in tomopy_recon_algorithm_kwargs]
        self.tomopy_methods_list.remove("gridrec")
        self.tomopy_methods_list.remove("fbp")
        self.astra_cuda_methods_list = [
            key for key in astra_cuda_recon_algorithm_kwargs
        ]
        self.metadata = Metadata_Align()
        self.run_list = []
        self.header_font_style = {
            "font_size": "22px",
            "font_weight": "bold",
            "font_variant": "small-caps",
            # "text_color": "#0F52BA",
        }
        self.accordions_open = False
        self.plot_output1 = Output()

    def init_widgets(self):
        """
        Initializes many of the widgets in the Alignment and Recon tabs.
        """
        self.button_font = {"font_size": "22px"}
        self.button_layout = Layout(width="45px", height="40px")

        # -- Button to turn on tab ---------------------------------------------
        self.open_accordions_button = Button(
            icon="lock-open",
            layout=self.button_layout,
            style=self.button_font,
        )

        # -- Headers for plotting -------------------------------------
        self.import_plot_header = "Imported Projections"
        self.import_plot_header = Label(
            self.import_plot_header, style=self.header_font_style
        )
        self.altered_plot_header = "Altered Projections"
        self.altered_plot_header = Label(
            self.altered_plot_header, style=self.header_font_style
        )

        # -- Headers for results -------------------------------------
        self.before_analysis_plot_header = "Analysis Projections"
        self.before_analysis_plot_header = Label(
            self.before_analysis_plot_header, style=self.header_font_style
        )
        self.after_analysis_plot_header = "Result"
        self.after_analysis_plot_header = Label(
            self.after_analysis_plot_header, style=self.header_font_style
        )

        # -- Button for using imported dataset  ---------------------------------
        self.use_imported_button = Button(
            description="Click here to use the imported data for analysis.",
            layout=Layout(width="auto"),
        )

        # -- Button for using edited dataset  ---------------------------------
        self.use_altered_button = Button(
            description="Click here to use the altered data for analysis.",
            layout=Layout(width="auto"),
        )

        # -- Button to load metadata ----------------------------------------------
        self.load_metadata_button = Button(
            description="Click to load metadata.",
            icon="upload",
            disabled=True,
            button_style="info",  # 'success', 'info', 'warning', 'danger' or ''
            tooltip="First choose a metadata file in the Import tab, then click here",
            layout=Layout(width="auto", justify_content="center"),
        )

        # -- Plotting -------------------------------------------------------------
        self.set_range_button = Button(
            description="Click to set current range to analysis range.",
            layout=Layout(width="auto"),
        )

        self.viewer_hbox = HBox(
            [
                VBox(
                    [
                        self.import_plot_header,
                        self.imported_viewer.app,
                        self.use_imported_button,
                    ],
                    layout=Layout(align_items="center"),
                ),
                VBox(
                    [
                        self.altered_plot_header,
                        self.altered_viewer.app,
                        self.use_altered_button,
                    ],
                    layout=Layout(align_items="center"),
                ),
            ],
            layout=Layout(justify_content="center"),
        )

        self.viewer_accordion = Accordion(
            children=[self.viewer_hbox],
            selected_index=None,
            titles=("Plot Projection Images",),
        )

        # -- Saving Options -------------------------------------------------------
        self.save_opts = {key: False for key in self.save_opts_list}
        self.save_opts_checkboxes = self.create_checkboxes_from_opt_list(
            self.save_opts_list, self.save_opts
        )

        # -- Method Options -------------------------------------------------------
        self.methods_opts = {
            key: False
            for key in self.tomopy_methods_list + self.astra_cuda_methods_list
        }
        self.tomopy_methods_checkboxes = self.create_checkboxes_from_opt_list(
            self.tomopy_methods_list, self.methods_opts
        )
        self.astra_cuda_methods_checkboxes = self.create_checkboxes_from_opt_list(
            self.astra_cuda_methods_list, self.methods_opts
        )

        # -- Options ----------------------------------------------------------

        # Number of iterations
        self.num_iterations_textbox = IntText(
            description="Number of Iterations: ",
            style=extend_description_style,
            value=self.num_iter,
        )

        # Center
        self.center_textbox = FloatText(
            description="Center of Rotation: ",
            style=extend_description_style,
            value=self.center,
        )
        center_link = link(
            (self.center_textbox, "value"), (self.Center.center_textbox, "value")
        )

        # Downsampling
        self.downsample_checkbox = Checkbox(description="Downsample?", value=False)
        self.downsample_factor_textbox = BoundedFloatText(
            value=self.downsample_factor,
            min=0.001,
            max=1.0,
            description="Downsample factor:",
            disabled=True,
            style=extend_description_style,
        )

        # Phase cross correlation subset (from altered projections)
        self.use_subset_correlation_checkbox = Checkbox(
            description="Phase Corr. Subset?", value=False
        )

        # Batch size
        self.num_batches_textbox = IntText(
            description="Number of batches (for GPU): ",
            style=extend_description_style,
            value=self.num_batches,
        )

        # X Padding
        self.paddingX_textbox = IntText(
            description="Padding X (px): ",
            style=extend_description_style,
            value=self.paddingX,
        )

        # Y Padding
        self.paddingY_textbox = IntText(
            description="Padding Y (px): ",
            style=extend_description_style,
            value=self.paddingY,
        )

        # Pre-alignment iterations
        self.pre_alignment_iters_textbox = IntText(
            description="Pre-alignment iterations: ",
            style=extend_description_style,
            value=self.pre_alignment_iters,
        )

        # Extra options
        self.extra_options_textbox = Text(
            description="Extra options: ",
            placeholder='{"MinConstraint": 0}',
            style=extend_description_style,
        )

    def refresh_plots(self):
        self.imported_viewer.plot()

    def set_observes(self):

        # -- Radio to turn on tab ---------------------------------------------
        self.open_accordions_button.on_click(self.activate_tab)

        # -- Button for using imported dataset  ---------------------------------
        self.use_imported_button.on_click(self.use_imported)

        # -- Button for using edited dataset  ---------------------------------
        self.use_altered_button.on_click(self.use_altered)

        # -- Load metadata button ---------------------------------------------
        self.load_metadata_button.on_click(self._load_metadata_all_on_click)

        # -- Options ----------------------------------------------------------

        # Center
        self.center_textbox.observe(self.update_center_textbox, names="value")

        # Downsampling
        self.downsample_checkbox.observe(self._downsample_turn_on)
        self.downsample_factor_textbox.observe(
            self.update_downsample_factor_dict, names="value"
        )

        # Phase cross correlation subset (from altered projections)
        self.use_subset_correlation_checkbox.observe(self._use_subset_correlation)

        # X Padding
        self.paddingX_textbox.observe(self.update_x_padding, names="value")

        # Y Padding
        self.paddingY_textbox.observe(self.update_y_padding, names="value")

        # Pre-alignment iterations
        self.pre_alignment_iters_textbox.observe(
            self.update_pre_alignment_iters, names="value"
        )

        # Extra options
        self.extra_options_textbox.observe(self.update_extra_options, names="value")

        # Start button
        self.start_button.on_click(self.set_options_and_run)

    # -- Radio to turn on tab ---------------------------------------------
    def activate_tab(self, *args):
        if self.accordions_open is False:
            self.open_accordions_button.icon = "fa-lock"
            self.open_accordions_button.button_style = "success"
            self.projections = self.Import.projections
            self.center = self.Center.current_center
            self.center_textbox.value = self.Center.current_center
            self.metadata.set_metadata(self)
            self.load_metadata_button.disabled = False
            self.start_button.disabled = False
            self.save_options_accordion.selected_index = 0
            self.options_accordion.selected_index = 0
            self.methods_accordion.selected_index = 0
            self.viewer_accordion.selected_index = 0
            self.log.info("Activated alignment.")
            self.accordions_open = True
        else:
            self.open_accordions_button.icon = "fa-lock-open"
            self.open_accordions_button.button_style = "info"
            self.accordions_open = False
            self.load_metadata_button.disabled = True
            self.start_button.disabled = True
            self.save_options_accordion.selected_index = None
            self.options_accordion.selected_index = None
            self.methods_accordion.selected_index = None
            self.viewer_accordion.selected_index = None
            self.log.info("Deactivated alignment.")

    # -- Button for using imported dataset  ---------------------------------
    def use_imported(self, *args):
        self.use_altered_button.icon = ""
        self.use_altered_button.button_style = ""
        self.use_imported_button.button_style = "info"
        self.use_imported_button.description = "Creating analysis projections"
        self.use_imported_button.icon = "fas fa-cog fa-spin fa-lg"
        self.projections.data = copy.deepcopy(self.Import.projections.data)
        self.projections.angles_rad = copy.deepcopy(self.Import.projections.angles_rad)
        self.projections.angles_deg = copy.deepcopy(self.Import.projections.angles_deg)
        self.pixel_range_x = self.projections.pixel_range_x
        self.pixel_range_y = self.projections.pixel_range_y
        self.result_before_viewer = self.imported_viewer
        self.result_after_viewer = BqImViewer_DataExplorer_AfterAnalysis(
            self.result_before_viewer
        )
        self.use_imported_button.button_style = "success"
        self.use_imported_button.description = (
            "You can now align/reconstruct your data."
        )
        self.use_imported_button.icon = "fa-check-square"

    # -- Button for using edited dataset  ---------------------------------
    def use_altered(self, *args):
        self.use_imported_button.icon = ""
        self.use_imported_button.button_style = ""
        self.use_altered_button.button_style = "info"
        self.use_altered_button.description = "Creating analysis projections"
        self.use_altered_button.icon = "fas fa-cog fa-spin fa-lg"
        self.projections._data = self.altered_viewer.original_imagestack
        self.projections.data = self.altered_viewer.original_imagestack
        self.projections.angles_rad = copy.deepcopy(self.Import.projections.angles_rad)
        self.projections.angles_deg = copy.deepcopy(self.Import.projections.angles_deg)
        self.pixel_range_x = self.altered_viewer.pixel_range_x
        self.pixel_range_y = self.altered_viewer.pixel_range_y
        self.result_before_viewer = self.altered_viewer
        self.result_after_viewer = BqImViewer_DataExplorer_AfterAnalysis(
            self.result_before_viewer
        )
        self.use_altered_button.button_style = "success"
        self.use_altered_button.description = "You can now align/reconstruct your data."
        self.use_altered_button.icon = "fa-check-square"

    # -- Load metadata button ---------------------------------------------
    def _load_metadata_all_on_click(self, change):
        self.load_metadata_button.button_style = "info"
        self.load_metadata_button.icon = "fas fa-cog fa-spin fa-lg"
        self.load_metadata_button.description = "Importing metadata."
        self.load_metadata_align()
        self.metadata.set_attributes_from_metadata()
        # self = _set_widgets_from_load_metadata(self)
        self.set_observes()
        self.load_metadata_button.button_style = "success"
        self.load_metadata_button.icon = "fa-check-square"
        self.load_metadata_button.description = "Finished importing metadata."

    # -- Button to start alignment ----------------------------------------
    def set_options_and_run(self, change):
        change.button_style = "info"
        change.icon = "fas fa-cog fa-spin fa-lg"
        change.description = (
            "Setting options and loading data into alignment algorithm."
        )
        self.run()
        change.button_style = "success"
        change.icon = "fa-check-square"
        change.description = "Finished alignment."

    # -- Options ----------------------------------------------------------

    # Number of iterations
    def update_num_iter(self, change):
        self.num_iter = int(change.new)
        self.progress_total.max = change.new
        self.metadata.set_metadata(self)

    # Center of rotation
    def update_center_textbox(self, change):
        self.center = change.new
        self.metadata.set_metadata(self)

    # Downsampling
    def _downsample_turn_on(self, change):
        if change.new is True:
            self.downsample = True
            self.downsample_factor = self.downsample_factor_textbox.value
            self.downsample_factor_textbox.disabled = False
            self.metadata.set_metadata(self)
        if change.new is False:
            self.downsample = False
            self.downsample_factor = 1
            self.downsample_factor_textbox.value = 1
            self.downsample_factor_textbox.disabled = True
            self.metadata.set_metadata(self)

    # Phase cross correlation subset (from altered projections)
    def _use_subset_correlation(self, change):
        self.use_subset_correlation = change.new
        self.metadata.set_metadata(self)

    def update_downsample_factor_dict(self, change):
        self.downsample_factor = change.new
        self.metadata.set_metadata(self)

    # Batch size
    def update_num_batches(self, change):
        self.num_batches = change.new
        self.progress_phase_cross_corr.max = change.new
        self.progress_shifting.max = change.new
        self.progress_reprj.max = change.new
        self.metadata.set_metadata(self)

    # X Padding
    def update_x_padding(self, change):
        self.paddingX = change.new
        self.metadata.set_metadata(self)

    # Y Padding
    def update_y_padding(self, change):
        self.paddingY = change.new
        self.metadata.set_metadata(self)

    # Pre-alignment iterations
    def update_pre_alignment_iters(self, *args):
        self.pre_alignment_iters = self.pre_alignment_iters_textbox.value

    # Extra options
    def update_extra_options(self, change):
        self.extra_options = change.new
        self.metadata.set_metadata(self)

    # def set_widgets_from_load_metadata(self):

    #     # -- Saving Options -------------------------------------------------------
    #     self.save_opts_checkboxes = self.set_checkbox_bool(
    #         self.save_opts_checkboxes, self.metadata["save_opts"]
    #     )

    #     # -- Method Options -------------------------------------------------------
    #     # for key in self.metadata["methods"]:
    #     #     if self.metadata["methods"][key]:
    #     #         for checkbox in self.methods_checkboxes:
    #     #             if checkbox.description == str(key):
    #     #                 checkbox.value = True
    #     #     elif not self.metadata["methods"][key]:
    #     #         for checkbox in self.methods_checkboxes:
    #     #             if checkbox.description == str(key):
    #     #                 checkbox.value = False

    #     self.tomopy_methods_checkboxes = self.set_checkbox_bool(
    #         self.tomopy_methods_checkboxes, self.metadata["methods"]
    #     )
    #     self.astra_cuda_methods_checkboxes = self.set_checkbox_bool(
    #         self.astra_cuda_methods_checkboxes, self.metadata["methods"]
    #     )

    #     # -- Projection Range Sliders ---------------------------------------------
    #     # Not implemented in load metadata.

    #     # -- Options ----------------------------------------------------------

    #     # Number of iterations
    #     self.num_iterations_textbox.value = self.num_iter

    #     # Center
    #     self.center_textbox.value = self.center

    #     # Downsampling
    #     self.downsample_checkbox.value = self.downsample
    #     self.downsample_factor_textbox.value = self.downsample_factor
    #     if self.downsample_checkbox.value:
    #         self.downsample_factor_textbox.disabled = False

    #     # Batch size
    #     self.num_batches_textbox.value = self.num_batches

    #     # X Padding
    #     self.paddingX_textbox.value = self.paddingX

    #     # Y Padding
    #     self.paddingY_textbox.value = self.paddingY

    #     # Extra options
    #     self.extra_options_textbox.value = str(self.extra_options)
    #     return self

    def set_checkbox_bool(self, checkbox_list, dictionary):
        def create_opt_dict_on_check(change):
            dictionary[change.owner.description] = change.new
            self.metadata.set_metadata(self)

        for key in dictionary:
            if dictionary[key]:
                for checkbox in checkbox_list:
                    if checkbox.description == str(key):
                        checkbox.value = True
                        checkbox.observe(create_opt_dict_on_check, names="value")
            elif not dictionary[key]:
                for checkbox in checkbox_list:
                    if checkbox.description == str(key):
                        checkbox.value = False
                        checkbox.observe(create_opt_dict_on_check, names="value")
        return checkbox_list

    def create_checkboxes_from_opt_list(self, opt_list, dictionary):
        checkboxes = [MetaCheckbox(opt, dictionary, self) for opt in opt_list]
        return [a.checkbox for a in checkboxes]  # return list of checkboxes

    def plot_result(self):
        with self.plot_output1:
            self.plot_output1.clear_output(wait=True)
            self.output_hbox = HBox(
                [
                    VBox(
                        [
                            self.before_analysis_plot_header,
                            self.result_before_viewer.app,
                        ],
                        layout=Layout(align_items="center"),
                    ),
                    VBox(
                        [
                            self.after_analysis_plot_header,
                            self.result_after_viewer.app,
                        ],
                        layout=Layout(align_items="center"),
                    ),
                ],
                layout=Layout(justify_content="center"),
            )
            display(self.output_hbox)

    @abstractmethod
    def update_num_batches(self, *args):
        ...

    @abstractmethod
    def update_num_iter(self, *args):
        ...

    @abstractmethod
    def run(self):
        ...

    @abstractmethod
    def make_tab(self):
        ...

    # TODO: add @abstractmethod for loading metadata


class Align(AnalysisBase):
    def __init__(self, Import, Center):
        super().init_attributes(Import, Center)
        self.subset_range_x = None
        self.subset_range_y = None
        self.save_opts_list = ["tomo_after", "tomo_before", "recon", "tiff", "npy"]
        self.Import.Align = self
        self.init_widgets()
        self.metadata.set_metadata(self)
        self.set_observes()
        self.make_tab()

    def init_widgets(self):
        super().init_widgets()

        # -- Progress bars and plotting output --------------------------------
        self.progress_total = IntProgress(description="Recon: ", value=0, min=0, max=1)
        self.progress_reprj = IntProgress(description="Reproj: ", value=0, min=0, max=1)
        self.progress_phase_cross_corr = IntProgress(
            description="Phase Corr: ", value=0, min=0, max=1
        )
        self.progress_shifting = IntProgress(
            description="Shifting: ", value=0, min=0, max=1
        )
        self.plot_output2 = Output()

        # -- Button to start alignment ----------------------------------------
        self.start_button = Button(
            description="After choosing all of the options above, click this button to start the alignment.",
            disabled=True,
            button_style="info",  # 'success', 'info', 'warning', 'danger' or ''
            tooltip="Start alignment.",
            icon="",
            layout=Layout(width="auto", justify_content="center"),
        )
        # -- Upsample factor --------------------------------------------------
        self.upsample_factor_textbox = FloatText(
            description="Upsample Factor: ",
            style=extend_description_style,
            value=self.upsample_factor,
        )

    def set_observes(self):
        super().set_observes()
        self.num_iterations_textbox.observe(self.update_num_iter, names="value")
        self.num_batches_textbox.observe(self.update_num_batches, names="value")
        self.upsample_factor_textbox.observe(self.update_upsample_factor, names="value")
        self.start_button.on_click(self.set_options_and_run)

    # Upsampling
    def update_upsample_factor(self, change):
        self.upsample_factor = change.new
        self.metadata.set_metadata(self)

    # TODO: implement load metadata
    # def set_widgets_from_load_metadata(self):
    #     super().set_widgets_from_load_metadata()
    #     # -- Upsample factor --------------------------------------------------
    #     self.upsample_factor_textbox.value = self.upsample_factor

    # TODO: implement load metadata
    # def load_metadata(self):
    #     self.metadata = load_metadata(
    #         self.Import.filedir_align, self.Import.filename_align
    #     )

    def update_num_batches(self, change):
        self.num_batches = change.new
        self.progress_phase_cross_corr.max = change.new
        self.progress_shifting.max = change.new
        self.progress_reprj.max = change.new
        self.metadata.set_metadata(self)

    def update_num_iter(self, change):
        self.num_iter = change.new
        self.progress_total.max = change.new
        self.metadata.set_metadata(self)

    def run(self):
        self.analysis = TomoAlign(self)
        self.analysis_projections = Projections_Prenormalized()
        self.analysis_projections.data = self.analysis.projections_aligned
        self.analysis_projections.filedir = self.analysis.wd
        self.result_after_viewer.create_app()
        self.result_after_viewer.plot(self.analysis_projections)
        self.plot_result()

    def make_tab(self):

        # -- Saving -----------------------------------------------------------
        save_hbox = HBox(
            self.save_opts_checkboxes,
            layout=Layout(flex_wrap="wrap", justify_content="space-between"),
        )

        self.save_options_accordion = Accordion(
            children=[save_hbox],
            selected_index=None,
            titles=("Save Options",),
        )

        # -- Methods ----------------------------------------------------------
        tomopy_methods_hbox = HBox(
            [
                Label("Tomopy:", layout=Layout(width="200px", align_content="center")),
                HBox(
                    self.tomopy_methods_checkboxes,
                    layout=widgets.Layout(flex_flow="row wrap"),
                ),
            ]
        )

        astra_methods_hbox = HBox(
            [
                Label("Astra:", layout=Layout(width="100px", align_content="center")),
                HBox(
                    self.astra_cuda_methods_checkboxes,
                    layout=widgets.Layout(flex_flow="row wrap"),
                ),
            ]
        )

        recon_method_box = VBox(
            [tomopy_methods_hbox, astra_methods_hbox],
            layout=widgets.Layout(flex_flow="row wrap"),
        )
        self.methods_accordion = Accordion(
            children=[recon_method_box], selected_index=None, titles=("Methods",)
        )

        # -- Box organization -------------------------------------------------

        top_of_box_hb = HBox(
            [self.open_accordions_button, self.Import.switch_data_buttons],
            layout=Layout(
                width="auto",
                justify_content="flex-start",
            ),
        )
        start_button_hb = HBox(
            [self.start_button], layout=Layout(width="auto", justify_content="center")
        )

        self.options_accordion = Accordion(
            children=[
                HBox(
                    [
                        self.num_iterations_textbox,
                        self.center_textbox,
                        self.upsample_factor_textbox,
                        self.num_batches_textbox,
                        self.paddingX_textbox,
                        self.paddingY_textbox,
                        self.downsample_checkbox,
                        self.downsample_factor_textbox,
                        self.extra_options_textbox,
                        self.use_subset_correlation_checkbox,
                        self.pre_alignment_iters_textbox,
                    ],
                    layout=Layout(flex_flow="row wrap", justify_content="flex-start"),
                ),
            ],
            selected_index=None,
            titles=("Alignment Options",),
        )

        progress_hbox = HBox(
            [
                self.progress_total,
                self.progress_reprj,
                self.progress_phase_cross_corr,
                self.progress_shifting,
            ],
            layout=Layout(justify_content="center"),
        )

        self.tab = VBox(
            children=[
                top_of_box_hb,
                self.viewer_accordion,
                # TODO: implement load metadata again
                # self.load_metadata_button,
                self.methods_accordion,
                self.save_options_accordion,
                self.options_accordion,
                start_button_hb,
                progress_hbox,
                VBox(
                    [self.plot_output1, self.plot_output2],
                ),
            ]
        )


class Recon(AnalysisBase):
    def __init__(self, Import, Center):
        super().init_attributes(Import, Center)
        self.metadata = Metadata_Recon()
        self.save_opts_list = ["tomo_before", "recon", "tiff", "npy"]
        self.Import.Recon = self
        self.init_widgets()
        self.metadata.set_metadata(self)
        self.set_observes()
        self.make_tab()

    def init_widgets(self):
        super().init_widgets()
        self.plot_output2 = Output()

        # -- Button to start alignment ----------------------------------------
        self.start_button = Button(
            description="After choosing all of the options above, click this button to start the reconstruction.",
            disabled=True,
            button_style="info",  # 'success', 'info', 'warning', 'danger' or ''
            tooltip="Start reconstruction.",
            icon="",
            layout=Layout(width="auto", justify_content="center"),
        )

    def set_observes(self):
        super().set_observes()
        self.num_iterations_textbox.observe(self.update_num_iter, names="value")

    # TODO: implement load metadata
    # def load_metadata(self):
    #     self.metadata = load_metadata(
    #         self.Import.filedir_recon, self.Import.filename_recon
    #     )
    # TODO: implement load metadata
    # def set_widgets_from_load_metadata(self):
    #     super().set_widgets_from_load_metadata()
    #     self.init_widgets()
    #     self.metadata.set_metadata(self)
    #     self.make_tab()

    # Batch size
    def update_num_batches(self, change):
        self.num_batches = change.new
        self.metadata.set_metadata(self)

    # Number of iterations
    def update_num_iter(self, change):
        self.num_iter = change.new
        self.metadata.set_metadata(self)

    def run(self):
        self.analysis = TomoRecon(self)
        self.analysis_projections = Projections_Prenormalized_General()
        self.analysis_projections.data = self.analysis.recon
        self.analysis_projections.filedir = pathlib.Path(self.analysis.wd)
        self.result_after_viewer.create_app()
        self.result_after_viewer.plot(self.analysis_projections)
        self.plot_result()

    def make_tab(self):

        # -- Saving -----------------------------------------------------------
        save_hbox = HBox(
            self.save_opts_checkboxes,
            layout=Layout(flex_wrap="wrap", justify_content="space-between"),
        )

        self.save_options_accordion = Accordion(
            children=[save_hbox],
            selected_index=None,
            titles=("Save Options",),
        )

        # -- Methods ----------------------------------------------------------
        tomopy_methods_hbox = HBox(
            [
                Label("Tomopy:", layout=Layout(width="200px", align_content="center")),
                HBox(
                    self.tomopy_methods_checkboxes,
                    layout=widgets.Layout(flex_flow="row wrap"),
                ),
            ]
        )
        astra_methods_hbox = HBox(
            [
                Label("Astra:", layout=Layout(width="100px", align_content="center")),
                HBox(
                    self.astra_cuda_methods_checkboxes,
                    layout=widgets.Layout(flex_flow="row wrap"),
                ),
            ]
        )

        recon_method_box = VBox(
            [tomopy_methods_hbox, astra_methods_hbox],
            layout=widgets.Layout(flex_flow="row wrap"),
        )
        self.methods_accordion = Accordion(
            children=[recon_method_box], selected_index=None, titles=("Methods",)
        )

        # -- Box organization -------------------------------------------------

        top_of_box_hb = HBox(
            [self.open_accordions_button, self.Import.switch_data_buttons],
            layout=Layout(
                width="auto",
                justify_content="flex-start",
            ),
        )
        start_button_hb = HBox(
            [self.start_button], layout=Layout(width="auto", justify_content="center")
        )

        self.options_accordion = Accordion(
            children=[
                HBox(
                    [
                        self.num_iterations_textbox,
                        self.center_textbox,
                        self.paddingX_textbox,
                        self.paddingY_textbox,
                        self.downsample_checkbox,
                        self.downsample_factor_textbox,
                        self.extra_options_textbox,
                    ],
                    layout=Layout(
                        flex_flow="row wrap", justify_content="space-between"
                    ),
                ),
            ],
            selected_index=None,
            titles=("Alignment Options",),
        )

        self.tab = VBox(
            children=[
                top_of_box_hb,
                self.viewer_accordion,
                # TODO: implement load metadata again
                # self.load_metadata_button,
                self.methods_accordion,
                self.save_options_accordion,
                self.options_accordion,
                start_button_hb,
                self.plot_output1,
            ]
        )


class MetaCheckbox:
    def __init__(self, description, dictionary, obj, disabled=False, value=False):

        self.checkbox = Checkbox(
            description=description, value=value, disabled=disabled
        )

        def create_opt_dict_on_check(change):
            dictionary[description] = change.new
            obj.metadata.set_metadata(obj)  # obj needs a Metadata instance

        self.checkbox.observe(create_opt_dict_on_check, names="value")
