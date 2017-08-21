import numpy as np
import rasterio
from rasterio import Affine
from rasterio.warp import reproject, Resampling
import types


def get_8chan_SpectralClip(datapathPSRGB, datapathPSMUL, bs_rgb, bs_mul, imageid=[], debug=False):
    im = []

    with rasterio.open(datapathPSMUL, 'r') as f:
        # values = f.read().astype(np.float32)
        usechannels = [5, 3, 2, 2, 3, 6, 7, 8]
        for chan_i in usechannels:
            values = f.read(chan_i).astype(np.float32)
            min_val = np.min(values)
            max_val = np.max(values)
            mean_val = np.mean(values)
            values = np.clip(values, min_val, max_val)
            values = (values - min_val) / (max_val - min_val)
            im.append(values)

            if debug:
                print(values.shape)
                print(np.min(values))
                print(np.max(values))
    if debug:
        print('im[0] shape:')
        print(len(im))
    im = np.array(im)  # (ch, w, h)

    if debug:
        print(im.shape)

    return im


def get_8chan_SpectralClipAll(datapathPSRGB, datapathPSMUL, bs_rgb, bs_mul, imageid=[], debug=False):
    im = []

    with rasterio.open(datapathPSRGB, 'r') as f:
        usechannels = [1, 2, 3]
        for chan_i in usechannels:
            values = f.read(chan_i).astype(np.float32)
            min_val = np.min(values)
            max_val = np.max(values)
            values = np.clip(values, min_val, max_val)
            values = (values - min_val) / (max_val - min_val)
            values = values - np.mean(values)
            im.append(values)

    with rasterio.open(datapathPSMUL, 'r') as f:

        usechannels = [2, 3, 6, 7, 8]
        for chan_i in usechannels:
            values = f.read(chan_i).astype(np.float32)
            min_val = np.min(values)
            max_val = np.max(values)
            values = np.clip(values, min_val, max_val)
            values = (values - min_val) / (max_val - min_val)
            values = values - np.mean(values)
            im.append(values)

            if debug:
                print(values.shape)
                print(np.min(values))
                print(np.max(values))

    if debug:
        print('im[0] shape:')
        print(len(im))
    im = np.array(im)  # (ch, w, h)

    if debug:
        print(im.shape)

    return im


def resampleImage(src, array, spatialScaleFactor):
    # arr = src.read()
    newarr = np.empty(shape=(array.shape[0],  # same number of bands
                             round(array.shape[1] * spatialScaleFactor),  # 150% resolution
                             round(array.shape[2] * spatialScaleFactor)))

    # adjust the new affine transform to the 150% smaller cell size
    src_transform = src.affine
    dst_transform = Affine(src_transform.a / spatialScaleFactor, src_transform.b, src_transform.c,
                           src_transform.d, src_transform.e / spatialScaleFactor, src_transform.f)

    reproject(
        array, newarr,
        src_transform=src_transform,
        dst_transform=dst_transform,
        src_crs=src.crs,
        dst_crs=src.crs,
        resample=Resampling.bilinear)

    return newarr


def imageSlicer(image, strideInPixels, windowSize=[256, 256], debug=False, immean=np.array([])):
    # slide a window across the image
    for y in range(0, image.shape[1], strideInPixels):
        for x in range(0, image.shape[2], strideInPixels):
            # yield the current window
            if debug:
                print(image[:, y:y + windowSize[1], x:x + windowSize[0]].shape)

            if y + windowSize[1] > image.shape[1]:
                y = image.shape[1] - windowSize[1]

            if x + windowSize[0] > image.shape[2]:
                x = image.shape[2] - windowSize[0]

            if immean.size == 0:
                yield (image[:, y:y + windowSize[1], x:x + windowSize[0]])
            else:
                yield (image[:, y:y + windowSize[1], x:x + windowSize[0]] - immean)


def imageCombiner(listOfImages, image, strideInPixels, windowSize=[256, 256], debug=False):
    if debug:
        print(image.shape)
    newImage = np.empty(shape=(1,
                               image.shape[1],
                               image.shape[2]))

    newImageCount = np.empty(shape=(image.shape[0],
                                    image.shape[1],
                                    image.shape[2]))
    if isinstance(listOfImages, types.GeneratorType):
        listOfImages = list(listOfImages)
    idx = 0
    for y in range(0, image.shape[1], strideInPixels):
        for x in range(0, image.shape[2], strideInPixels):
            # yield the current window

            if y + windowSize[1] > image.shape[1]:
                y = image.shape[1] - windowSize[1]

            if x + windowSize[0] > image.shape[2]:
                x = image.shape[2] - windowSize[0]

            newImage[:, y:y + windowSize[1], x:x + windowSize[0]] += listOfImages[idx]

            newImageCount[:, y:y + windowSize[1], x:x + windowSize[0]] += 1

            idx += 1

    return newImage, newImageCount





