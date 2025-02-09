import numpy as np

# https://stackoverflow.com/questions/54567986/python-numpy-remove-empty-zeroes-border-of-3d-array


def pad_projections(prj, pad):
    npad = ((0, 0), ((pad[1]), pad[1]), (pad[0], pad[0]))
    prj = np.pad(prj, npad, mode="constant", constant_values=0)
    return prj


def trim_padding(prj):

    xs, ys, zs = np.where(np.absolute(prj) > 1e-7)

    minxs = np.min(xs)
    maxxs = np.max(xs)
    minys = np.min(ys)
    maxys = np.max(ys)
    minzs = np.min(zs)
    maxzs = np.max(zs)

    # extract cube with extreme limits of where are the values != 0
    result = prj[minxs : maxxs + 1, minys : maxys + 1, minzs : maxzs + 1]
    # not sure why +1 here.

    return result


# https://stackoverflow.com/questions/24806174/is-there-an-opposite-inverse-to-numpy-pad-function
def unpad_rec_with_pad(rec, pad):
    # padding in z is from the projection y padding
    # padding in x is from the projection x padding
    npad = ((pad[1], pad[1]), (pad[0], pad[0]), (pad[0], pad[0]))
    slices = []
    for c in npad:
        e = None if c[1] == 0 else -c[1]
        slices.append(slice(c[0], e))
    return rec[tuple(slices)]


def pad_to_make_same_size(images_to_pad, images):
    to_pad_shape = images_to_pad.shape
    reference_shape = images.shape
    diffshape = [y - x for x, y in zip(to_pad_shape, reference_shape)]
    diffshape = [
        [x / 2, x / 2] if x % 2 == 0 else [x / 2 + 0.5, x / 2 - 0.5] for x in diffshape
    ]
    pad = tuple([(int(x[0]), int(x[1])) for x in diffshape])
    images_padded = np.pad(images_to_pad, pad)
    return images_padded
