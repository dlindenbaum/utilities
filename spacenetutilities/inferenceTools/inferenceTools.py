import numpy as np
import rasterio
from rasterio import Affine
from rasterio.warp import reproject, Resampling
import types
import tqdm
from rasterio.windows import Window
from rasterio.coords import BoundingBox



### image sampling rules
def get_8chan_SpectralClip_V5_file(datapathPSMUL, bs_mul, debug=False):
    return get_8chan_SpectralClip_file(datapathPSMUL,
                                  bs_mul,
                                  bandChannels=[5, 3, 2, 2, 3, 6, 7, 8],
                                  debug=debug)


def get_8chan_SpectralClip_file(datapathPSMUL,
                           bs_mul,
                           bandChannels=[1, 2, 3, 4, 5, 6, 7, 8],
                           debug=False):


    with rasterio.open(datapathPSMUL, 'r') as f:

        if debug:
            print("Bands to ProcessbandChannels: {}".format(bandChannels))

        data = f.read().astype(np.float32)

    im = get_8chan_SpectralClip(data,
                                      bs_mul=bs_mul,
                                      bandChannels=bandChannels,
                                      debug=debug)


    if debug:
        print(im.shape)

    return im

def get_8chan_SpectralClip_V5(data, bs_mul, debug=False):

    return get_8chan_SpectralClip(data,
                                  bs_mul,
                                  bandChannels=[5, 3, 2, 2, 3, 6, 7, 8],
                                  debug=debug)

def get_8chan_SpectralClip(data,
                           bs_mul,
                           bandChannels=[1, 2, 3, 4, 5, 6, 7, 8],
                           debug=False):

    #bandChannels are in GDAL Raster Index First band = 1


    if debug:
        print("Bands to ProcessbandChannels: {}".format(bandChannels))

    for chan_i in bandChannels:
        min_val = bs_mul[chan_i - 1]['min']
        max_val = bs_mul[chan_i - 1]['max']
        data[chan_i - 1] = np.clip(data[chan_i-1], min_val, max_val)
        data[chan_i - 1] = (data[chan_i-1] - min_val) / (max_val - min_val)

        if debug:
            print('Processing channel {}'.format(chan_i))
            print(data[chan_i - 1].shape)
            print(np.min(data[chan_i - 1]))
            print(np.max(data[chan_i - 1]))



    if debug:
        print('data[0] shape:')
        print(len(data))

    if debug:
        print(data.shape)

    return data




def resampleImage(array, spatialScaleFactor, src_meta=[], src_transform=[], src_crs=[], dst_transform=[],
                  newarr=np.array([])):
    # with rasterio.open('path/to/file.tif') as src:
    #   src_meta= src.meta
    # or
    # src_transform = src.affine
    # src_crs = src.crs
    if newarr.size == 0:
        newarr = np.empty(shape=(array.shape[0],  # same number of bands
                                 round(array.shape[1] * spatialScaleFactor),  # 150% resolution
                                 round(array.shape[2] * spatialScaleFactor)))

    # adjust the new affine transform to the 150% smaller cell size
    if src_meta:
        src_transform = src_meta['transform']
        src_crs = src_meta['crs']
    else:
        if not src_transform or not src_crs:
            print('Error src transform and src_crs must be defined if src file is not defined')
            return -1


    if not dst_transform:
        dst_transform = Affine(src_transform.a / spatialScaleFactor, src_transform.b, src_transform.c,
                               src_transform.d, src_transform.e / spatialScaleFactor, src_transform.f)

    reproject(
        array, newarr,
        src_transform=src_transform,
        dst_transform=dst_transform,
        src_crs=src_crs,
        dst_crs=src_crs,
        resample=Resampling.bilinear)

    return newarr, dst_transform, src_crs, src_transform, src_crs


def imageSlicer(image, strideInPixels, windowSize=(256, 256), debug=False, immean=np.array([])):
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


def imageSlicerBatchGenerator(image, strideInPixels, windowSize=(256, 256), debug=False,
                              immean=np.array([]),
                              batchSize=32,
                              enable_tqdm=False,
                              infGenerator=True):
    print('Deprecated')
    ## TODO not working
    # slide a window across the image
    idx = 1
    X_batch = []
    for y in range(0, image.shape[1], strideInPixels):
        for x in range(0, image.shape[2], strideInPixels):
            # yield the current window

            if y + windowSize[1] >= image.shape[1]:
                y = image.shape[1] - windowSize[1]

            if x + windowSize[1] >= image.shape[1]:
                x = image.shape[2] - windowSize[0]

            if debug:
                print(image[:, y:y + windowSize[1], x:x + windowSize[0]].shape)

            X_batch.append(image[:, y:y + windowSize[1], x:x + windowSize[0]] - immean)

            if idx % batchSize == 0:
                idx += 1
                if debug:
                    print("x={}, y={}".format(x, y))
                    print("Length of XBatch = {}".format(len(X_batch)))
                if immean.size == 0:
                    final = np.array(X_batch)

                else:
                    final = np.array(X_batch) - immean

                if debug:
                    print("Final shape = {}".format(final.shape))
                    print("Final idx = {}".format(idx))

                X_batch = []

                yield (final, np.zeros(shape=final.shape))
            else:
                idx += 1

    while infGenerator:
        if len(X_batch) < batchSize:
            for idx1 in range(batchSize - len(X_batch)):
                X_batch.append(np.zeros(shape=image[:, y:y + windowSize[1], x:x + windowSize[0]].shape))

            if immean.size == 0:
                final = np.array(X_batch)

            else:
                final = np.array(X_batch) - immean

            if debug:
                print("Final shape = {}".format(final.shape))
                print("Final idx = {}".format(idx))

            yield (final, np.zeros(shape=final.shape))


def imageSlicerBatchGenerator_Single(image,
                               strideInPixels,
                               windowSize=(256, 256),
                               debug=False,
                               immean=np.array([]),
                               batchSize=1,
                               enable_tqdm=False,
                               pbar=[]
                               ):

        # slide a window across the image
    idx = 0
    X_batch = []
    for y in range(0, image.shape[1], strideInPixels):
        for x in range(0, image.shape[2], strideInPixels):
            # yield the current window
            idx += 1
            X_batch = []
            if y + windowSize[1] >= image.shape[1]:
                y = image.shape[1] - windowSize[1]

            if x + windowSize[1] >= image.shape[2]:
                x = image.shape[2] - windowSize[0]

            if debug:
                print(image[:, y:y + windowSize[1], x:x + windowSize[0]].shape)

            X_batch.append(image[:, y:y + windowSize[1], x:x + windowSize[0]] - immean)

            if debug:
                print("x={}, y={}".format(x, y))
                print("Length of XBatch = {}".format(len(X_batch)))
            if immean.size == 0:
                final = np.array(X_batch)

            else:
                final = np.array(X_batch) - immean

            if debug:
                print("Final shape = {}".format(final.shape))
                print('idx = {}'.format(idx))

            if enable_tqdm:
                pbar.update(final.shape[0])

            yield (final, np.zeros(shape=final.shape))




def imageSlicerBatchCounter(image,
                            strideInPixels,
                            windowSize=(256, 256),
                            debug=False,
                            immean=np.array([]),
                            batchSize=32):
    # slide a window across the image
    batchIncrement = 0
    X_batch = []
    idx = len(range(0, image.shape[1], strideInPixels)) * len(range(0, image.shape[2], strideInPixels))

    return idx, batchIncrement


def imageCombiner(listOfImages, image, strideInPixels, windowSize=(256, 256), debug=False):
    if debug:
        print(image.shape)
    newImage = np.empty(shape=(1,
                               image.shape[1],
                               image.shape[2]))

    newImageCount = np.empty(shape=(1,
                                    image.shape[1],
                                    image.shape[2]))
    if isinstance(listOfImages, types.GeneratorType):
        listOfImages = list(listOfImages)
    idx = 0
    for y in range(0, image.shape[1], strideInPixels):
        for x in range(0, image.shape[2], strideInPixels):
            if y + windowSize[1] > image.shape[1]:
                y = image.shape[1] - windowSize[1]

            if x + windowSize[0] > image.shape[2]:
                x = image.shape[2] - windowSize[0]

            newImage[:, y:y + windowSize[1], x:x + windowSize[0]] += listOfImages[idx]

            newImageCount[:, y:y + windowSize[1], x:x + windowSize[0]] += 1

            idx += 1

    return newImage, newImageCount



def sceneTilerGenerator(datapathPSMUL, windowSize, percentOverlap=1.0, debug=False):

    with rasterio.open(datapathPSMUL, 'r') as src:

        src_meta = src.meta
        srcShape = src.shape

        strideInPixels = round(percentOverlap * windowSize[0])
        for y in range(0, srcShape[0], strideInPixels):
            for x in range(0, srcShape[1], strideInPixels):
                readWindow = Window(y, x, windowSize[0], windowSize[1]),
                # yield the current window
                array = src.read(window=readWindow)
                if debug:
                    print(array.shape)

                tmp_meta = src_meta
                tmp_meta['transform'] = src.window_transform(readWindow)
                tmp_meta['bounds'] = BoundingBox(*src.window_bounds(readWindow))

                yield (array, tmp_meta, readWindow)


