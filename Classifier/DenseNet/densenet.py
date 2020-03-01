'''DenseNet models for Keras.

# Reference

- [Densely Connected Convolutional Networks](https://arxiv.org/pdf/1608.06993.pdf)

- [The One Hundred Layers Tiramisu: Fully Convolutional DenseNets for Semantic Segmentation](https://arxiv.org/pdf/1611.09326.pdf)

'''

from __future__ import print_function

from __future__ import absolute_import

from __future__ import division



import warnings



from keras.models import Model

from keras.layers.core import Dense, Dropout, Activation, Reshape

from keras.layers.convolutional import Conv2D, Conv2DTranspose, UpSampling2D

from keras.layers.pooling import AveragePooling2D, MaxPooling2D

from keras.layers.pooling import GlobalAveragePooling2D

from keras.layers import Input

from keras.layers.merge import concatenate

from keras.layers.normalization import BatchNormalization

from keras.regularizers import l2

from keras.utils.layer_utils import convert_all_kernels_in_model, convert_dense_weights_data_format

from keras.utils.data_utils import get_file

from keras.engine.topology import get_source_inputs

from keras_applications.imagenet_utils import _obtain_input_shape

from keras_applications.imagenet_utils import decode_predictions

import keras.backend as K

from keras import backend as K

from keras.engine import Layer

from keras.utils.generic_utils import get_custom_objects

from keras.backend import normalize_data_format


class SubPixelUpscaling(Layer):

    """ Sub-pixel convolutional upscaling layer based on the paper "Real-Time Single Image

    and Video Super-Resolution Using an Efficient Sub-Pixel Convolutional Neural Network"

    (https://arxiv.org/abs/1609.05158).

    This layer requires a Convolution2D prior to it, having output filters computed according to

    the formula :

        filters = k * (scale_factor * scale_factor)

        where k = a user defined number of filters (generally larger than 32)

              scale_factor = the upscaling factor (generally 2)

    This layer performs the depth to space operation on the convolution filters, and returns a

    tensor with the size as defined below.

    # Example :

    ```python

        # A standard subpixel upscaling block

        x = Convolution2D(256, 3, 3, padding='same', activation='relu')(...)

        u = SubPixelUpscaling(scale_factor=2)(x)

        [Optional]

        x = Convolution2D(256, 3, 3, padding='same', activation='relu')(u)

    ```

        In practice, it is useful to have a second convolution layer after the

        SubPixelUpscaling layer to speed up the learning process.

        However, if you are stacking multiple SubPixelUpscaling blocks, it may increase

        the number of parameters greatly, so the Convolution layer after SubPixelUpscaling

        layer can be removed.

    # Arguments

        scale_factor: Upscaling factor.

        data_format: Can be None, 'channels_first' or 'channels_last'.

    # Input shape

        4D tensor with shape:

        `(samples, k * (scale_factor * scale_factor) channels, rows, cols)` if data_format='channels_first'

        or 4D tensor with shape:

        `(samples, rows, cols, k * (scale_factor * scale_factor) channels)` if data_format='channels_last'.

    # Output shape

        4D tensor with shape:

        `(samples, k channels, rows * scale_factor, cols * scale_factor))` if data_format='channels_first'

        or 4D tensor with shape:

        `(samples, rows * scale_factor, cols * scale_factor, k channels)` if data_format='channels_last'.

    """


    def __init__(self, scale_factor=2, data_format=None, **kwargs):

        super(SubPixelUpscaling, self).__init__(**kwargs)

        self.scale_factor = scale_factor

        self.data_format = normalize_data_format(data_format)


    def build(self, input_shape):

        pass


    def call(self, x, mask=None):

        y = K_BACKEND.depth_to_space(x, self.scale_factor, self.data_format)

        return y


    def compute_output_shape(self, input_shape):

        if self.data_format == 'channels_first':

            b, k, r, c = input_shape

            return (b, k // (self.scale_factor ** 2), r * self.scale_factor, c * self.scale_factor)

        else:

            b, r, c, k = input_shape

            return (b, r * self.scale_factor, c * self.scale_factor, k // (self.scale_factor ** 2))


    def get_config(self):

        config = {'scale_factor': self.scale_factor,

                  'data_format': self.data_format}

        base_config = super(SubPixelUpscaling, self).get_config()

        return dict(list(base_config.items()) + list(config.items()))

get_custom_objects().update({'SubPixelUpscaling': SubPixelUpscaling})


DENSENET_121_WEIGHTS_PATH = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-121-32.h5'

DENSENET_161_WEIGHTS_PATH = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-161-48.h5'

DENSENET_169_WEIGHTS_PATH = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-169-32.h5'

DENSENET_121_WEIGHTS_PATH_NO_TOP = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-121-32-no-top.h5'

DENSENET_161_WEIGHTS_PATH_NO_TOP = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-161-48-no-top.h5'

DENSENET_169_WEIGHTS_PATH_NO_TOP = r'https://github.com/titu1994/DenseNet/releases/download/v3.0/DenseNet-BC-169-32-no-top.h5'



def preprocess_input(x, data_format=None):

    """Preprocesses a tensor encoding a batch of images.



    # Arguments

        x: input Numpy tensor, 4D.

        data_format: data format of the image tensor.



    # Returns

        Preprocessed tensor.

    """

    if data_format is None:

        data_format = K.image_data_format()

    assert data_format in {'channels_last', 'channels_first'}



    if data_format == 'channels_first':

        if x.ndim == 3:

            # 'RGB'->'BGR'

            x = x[::-1, ...]

            # Zero-center by mean pixel

            x[0, :, :] -= 103.939

            x[1, :, :] -= 116.779

            x[2, :, :] -= 123.68

        else:

            x = x[:, ::-1, ...]

            x[:, 0, :, :] -= 103.939

            x[:, 1, :, :] -= 116.779

            x[:, 2, :, :] -= 123.68

    else:

        # 'RGB'->'BGR'

        x = x[..., ::-1]

        # Zero-center by mean pixel

        x[..., 0] -= 103.939

        x[..., 1] -= 116.779

        x[..., 2] -= 123.68



    x *= 0.017 # scale values



    return x





def DenseNet(input_shape=None, depth=40, nb_dense_block=3, growth_rate=12, nb_filter=-1, nb_layers_per_block=-1,

             bottleneck=False, reduction=0.0, dropout_rate=0.0, weight_decay=1e-4, subsample_initial_block=False,

             include_top=True, weights=None, input_tensor=None,

             classes=10, activation='softmax'):



    if weights not in {'imagenet', None}:

        raise ValueError('The `weights` argument should be either '

                         '`None` (random initialization) or `cifar10` '

                         '(pre-training on CIFAR-10).')



    if weights == 'imagenet' and include_top and classes != 1000:

        raise ValueError('If using `weights` as ImageNet with `include_top`'

                         ' as true, `classes` should be 1000')



    if activation not in ['softmax', 'sigmoid']:

        raise ValueError('activation must be one of "softmax" or "sigmoid"')



    if activation == 'sigmoid' and classes != 1:

        raise ValueError('sigmoid activation can only be used when classes = 1')



    # Determine proper input shape

    input_shape = _obtain_input_shape(input_shape,

                                      default_size=32,

                                      min_size=8,

                                      data_format=K.image_data_format(),

                                      require_flatten=include_top)



    if input_tensor is None:

        img_input = Input(shape=input_shape)

    else:

        if not K.is_keras_tensor(input_tensor):

            img_input = Input(tensor=input_tensor, shape=input_shape)

        else:

            img_input = input_tensor



    x = __create_dense_net(classes, img_input, include_top, depth, nb_dense_block,

                           growth_rate, nb_filter, nb_layers_per_block, bottleneck, reduction,

                           dropout_rate, weight_decay, subsample_initial_block, activation)



    # Ensure that the model takes into account

    # any potential predecessors of `input_tensor`.

    if input_tensor is not None:

        inputs = get_source_inputs(input_tensor)

    else:

        inputs = img_input

    # Create model.

    model = Model(inputs, x, name='densenet')


    return model




def DenseNetImageNet121(input_shape=None,

                        bottleneck=True,

                        reduction=0.5,

                        dropout_rate=0.0,

                        weight_decay=1e-6,

                        include_top=True,

                        weights='imagenet',

                        input_tensor=None,

                        classes=1000,

                        activation='softmax'):

    return DenseNet(input_shape, depth=121, nb_dense_block=4, growth_rate=12, nb_filter=8,

                    nb_layers_per_block=[6, 12, 24, 16], bottleneck=bottleneck, reduction=reduction,

                    dropout_rate=dropout_rate, weight_decay=weight_decay, subsample_initial_block=True,

                    include_top=include_top, weights=weights, input_tensor=input_tensor,

                    classes=classes, activation=activation)





def DenseNetImageNet169(input_shape=None,

                        bottleneck=True,

                        reduction=0.5,

                        dropout_rate=0.0,

                        weight_decay=1e-6,

                        include_top=True,

                        weights='imagenet',

                        input_tensor=None,

                        classes=1000,

                        activation='softmax'):

    return DenseNet(input_shape, depth=169, nb_dense_block=4, growth_rate=12, nb_filter=8,

                    nb_layers_per_block=[6, 12, 32, 32], bottleneck=bottleneck, reduction=reduction,

                    dropout_rate=dropout_rate, weight_decay=weight_decay, subsample_initial_block=True,

                    include_top=include_top, weights=weights, input_tensor=input_tensor,

                    classes=classes, activation=activation)





def DenseNetImageNet201(input_shape=None,

                        bottleneck=True,

                        reduction=0.5,

                        dropout_rate=0.0,

                        weight_decay=1e-6,

                        include_top=True,

                        weights=None,

                        input_tensor=None,

                        classes=1000,

                        activation='softmax'):

    return DenseNet(input_shape, depth=201, nb_dense_block=4, growth_rate=16, nb_filter=8,

                    nb_layers_per_block=[6, 12, 48, 32], bottleneck=bottleneck, reduction=reduction,

                    dropout_rate=dropout_rate, weight_decay=weight_decay, subsample_initial_block=True,

                    include_top=include_top, weights=weights, input_tensor=input_tensor,

                    classes=classes, activation=activation)





def DenseNetImageNet264(input_shape=None,

                        bottleneck=True,

                        reduction=0.5,

                        dropout_rate=0.5,

                        weight_decay=1e-4,

                        include_top=True,

                        weights=None,

                        input_tensor=None,

                        classes=1000,

                        activation='softmax'):

    return DenseNet(input_shape, depth=201, nb_dense_block=4, growth_rate=16, nb_filter=8,

                    nb_layers_per_block=[6, 12, 64, 48], bottleneck=bottleneck, reduction=reduction,

                    dropout_rate=dropout_rate, weight_decay=weight_decay, subsample_initial_block=True,

                    include_top=include_top, weights=weights, input_tensor=input_tensor,

                    classes=classes, activation=activation)





def DenseNetImageNet161(input_shape=None,

                        bottleneck=True,

                        reduction=0.5,

                        dropout_rate=0.0,

                        weight_decay=1e-6,

                        include_top=True,

                        weights='imagenet',

                        input_tensor=None,

                        classes=1000,

                        activation='softmax'):

    return DenseNet(input_shape, depth=161, nb_dense_block=4, growth_rate=12, nb_filter=8,

                    nb_layers_per_block=[6, 12, 36, 24], bottleneck=bottleneck, reduction=reduction,

                    dropout_rate=dropout_rate, weight_decay=weight_decay, subsample_initial_block=True,

                    include_top=include_top, weights=weights, input_tensor=input_tensor,

                    classes=classes, activation=activation)





def __conv_block(ip, nb_filter, bottleneck=False, dropout_rate=None, weight_decay=1e-4):

    ''' Apply BatchNorm, Relu, 3x3 Conv2D, optional bottleneck block and dropout

    Args:

        ip: Input keras tensor

        nb_filter: number of filters

        bottleneck: add bottleneck block

        dropout_rate: dropout rate

        weight_decay: weight decay factor

    Returns: keras tensor with batch_norm, relu and convolution2d added (optional bottleneck)

    '''

    concat_axis = 1 if K.image_data_format() == 'channels_first' else -1



    x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(ip)

    x = Activation('relu')(x)



    if bottleneck:

        inter_channel = nb_filter * 4  # Obtained from https://github.com/liuzhuang13/DenseNet/blob/master/densenet.lua



        x = Conv2D(inter_channel, (1, 1), kernel_initializer='he_normal', padding='same', use_bias=False,

                   kernel_regularizer=l2(weight_decay))(x)

        x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(x)

        x = Activation('relu')(x)



    x = Conv2D(nb_filter, (3, 3), kernel_initializer='he_normal', padding='same', use_bias=False)(x)

    if dropout_rate:

        x = Dropout(dropout_rate)(x)



    return x





def __dense_block(x, nb_layers, nb_filter, growth_rate, bottleneck=False, dropout_rate=None, weight_decay=1e-4,

                  grow_nb_filters=True, return_concat_list=False):

    ''' Build a dense_block where the output of each conv_block is fed to subsequent ones

    Args:

        x: keras tensor

        nb_layers: the number of layers of conv_block to append to the model.

        nb_filter: number of filters

        growth_rate: growth rate

        bottleneck: bottleneck block

        dropout_rate: dropout rate

        weight_decay: weight decay factor

        grow_nb_filters: flag to decide to allow number of filters to grow

        return_concat_list: return the list of feature maps along with the actual output

    Returns: keras tensor with nb_layers of conv_block appended

    '''

    concat_axis = 1 if K.image_data_format() == 'channels_first' else -1



    x_list = [x]



    for i in range(nb_layers):

        cb = __conv_block(x, growth_rate, bottleneck, dropout_rate, weight_decay)

        x_list.append(cb)



        x = concatenate([x, cb], axis=concat_axis)



        if grow_nb_filters:

            nb_filter += growth_rate



    if return_concat_list:

        return x, nb_filter, x_list

    else:

        return x, nb_filter





def __transition_block(ip, nb_filter, compression=1.0, weight_decay=1e-4):

    ''' Apply BatchNorm, Relu 1x1, Conv2D, optional compression, dropout and Maxpooling2D

    Args:

        ip: keras tensor

        nb_filter: number of filters

        compression: calculated as 1 - reduction. Reduces the number of feature maps

                    in the transition block.

        dropout_rate: dropout rate

        weight_decay: weight decay factor

    Returns: keras tensor, after applying batch_norm, relu-conv, dropout, maxpool

    '''

    concat_axis = 1 if K.image_data_format() == 'channels_first' else -1



    x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(ip)

    x = Activation('relu')(x)

    x = Conv2D(int(nb_filter * compression), (1, 1), kernel_initializer='he_normal', padding='same', use_bias=False,

               kernel_regularizer=l2(weight_decay))(x)

    x = AveragePooling2D((2, 2), strides=(2, 2))(x)



    return x





def __transition_up_block(ip, nb_filters, type='deconv', weight_decay=1E-4):

    ''' SubpixelConvolutional Upscaling (factor = 2)

    Args:

        ip: keras tensor

        nb_filters: number of layers

        type: can be 'upsampling', 'subpixel', 'deconv'. Determines type of upsampling performed

        weight_decay: weight decay factor

    Returns: keras tensor, after applying upsampling operation.

    '''



    if type == 'upsampling':

        x = UpSampling2D()(ip)

    elif type == 'subpixel':

        x = Conv2D(nb_filters, (3, 3), activation='relu', padding='same', kernel_regularizer=l2(weight_decay),

                   use_bias=False, kernel_initializer='he_normal')(ip)

        x = SubPixelUpscaling(scale_factor=2)(x)

        x = Conv2D(nb_filters, (3, 3), activation='relu', padding='same', kernel_regularizer=l2(weight_decay),

                   use_bias=False, kernel_initializer='he_normal')(x)

    else:

        x = Conv2DTranspose(nb_filters, (3, 3), activation='relu', padding='same', strides=(2, 2),

                            kernel_initializer='he_normal', kernel_regularizer=l2(weight_decay))(ip)



    return x





def __create_dense_net(nb_classes, img_input, include_top, depth=40, nb_dense_block=3, growth_rate=12, nb_filter=-1,

                       nb_layers_per_block=-1, bottleneck=False, reduction=0.0, dropout_rate=None, weight_decay=1e-4,

                       subsample_initial_block=False, activation='softmax'):

    ''' Build the DenseNet model

    Args:

        nb_classes: number of classes

        img_input: tuple of shape (channels, rows, columns) or (rows, columns, channels)

        include_top: flag to include the final Dense layer

        depth: number or layers

        nb_dense_block: number of dense blocks to add to end (generally = 3)

        growth_rate: number of filters to add per dense block

        nb_filter: initial number of filters. Default -1 indicates initial number of filters is 2 * growth_rate

        nb_layers_per_block: number of layers in each dense block.

                Can be a -1, positive integer or a list.

                If -1, calculates nb_layer_per_block from the depth of the network.

                If positive integer, a set number of layers per dense block.

                If list, nb_layer is used as provided. Note that list size must

                be (nb_dense_block + 1)

        bottleneck: add bottleneck blocks

        reduction: reduction factor of transition blocks. Note : reduction value is inverted to compute compression

        dropout_rate: dropout rate

        weight_decay: weight decay rate

        subsample_initial_block: Set to True to subsample the initial convolution and

                add a MaxPool2D before the dense blocks are added.

        subsample_initial:

        activation: Type of activation at the top layer. Can be one of 'softmax' or 'sigmoid'.

                Note that if sigmoid is used, classes must be 1.

    Returns: keras tensor with nb_layers of conv_block appended

    '''



    concat_axis = 1 if K.image_data_format() == 'channels_first' else -1



    if reduction != 0.0:

        assert reduction <= 1.0 and reduction > 0.0, 'reduction value must lie between 0.0 and 1.0'



    # layers in each dense block

    if type(nb_layers_per_block) is list or type(nb_layers_per_block) is tuple:

        nb_layers = list(nb_layers_per_block)  # Convert tuple to list

        final_nb_layer = nb_layers[-1]

        nb_layers = nb_layers[:-1]

    else:

        if nb_layers_per_block == -1:

            assert (depth - 4) % 3 == 0, 'Depth must be 3 N + 4 if nb_layers_per_block == -1'

            count = int((depth - 4) / 3)



            if bottleneck:

                count = count // 2



            nb_layers = [count for _ in range(nb_dense_block)]

            final_nb_layer = count

        else:

            final_nb_layer = nb_layers_per_block

            nb_layers = [nb_layers_per_block] * nb_dense_block



    # compute initial nb_filter if -1, else accept users initial nb_filter

    if nb_filter <= 0:

        nb_filter = 2 * growth_rate



    # compute compression factor

    compression = 1.0 - reduction



    # Initial convolution

    if subsample_initial_block:

        initial_kernel = (7, 7)

        initial_strides = (2, 2)

    else:

        initial_kernel = (3, 3)

        initial_strides = (1, 1)



    x = Conv2D(nb_filter, initial_kernel, kernel_initializer='he_normal', padding='same',

               strides=initial_strides, use_bias=False, kernel_regularizer=l2(weight_decay))(img_input)



    if subsample_initial_block:

        x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(x)

        x = Activation('relu')(x)

        x = MaxPooling2D((3, 3), strides=(2, 2), padding='same')(x)



    # Add dense blocks

    for block_idx in range(nb_dense_block - 1):

        x, nb_filter = __dense_block(x, nb_layers[block_idx], nb_filter, growth_rate, bottleneck=bottleneck,

                                     dropout_rate=dropout_rate, weight_decay=weight_decay)

        # add transition_block

        x = __transition_block(x, nb_filter, compression=compression, weight_decay=weight_decay)

        nb_filter = int(nb_filter * compression)



    # The last dense_block does not have a transition_block

    x, nb_filter = __dense_block(x, final_nb_layer, nb_filter, growth_rate, bottleneck=bottleneck,

                                 dropout_rate=dropout_rate, weight_decay=weight_decay)



    x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(x)

    x = Activation('relu',name='feature')(x)

    x = GlobalAveragePooling2D()(x)



    if include_top:

        x = Dense(nb_classes, activation=activation)(x)



    return x





def __create_fcn_dense_net(nb_classes, img_input, include_top, nb_dense_block=5, growth_rate=12,

                           reduction=0.0, dropout_rate=None, weight_decay=1e-4,

                           nb_layers_per_block=4, nb_upsampling_conv=128, upsampling_type='upsampling',

                           init_conv_filters=48, input_shape=None, activation='deconv'):


    concat_axis = 1 if K.image_data_format() == 'channels_first' else -1



    if concat_axis == 1:  # channels_first dim ordering

        _, rows, cols = input_shape

    else:

        rows, cols, _ = input_shape



    if reduction != 0.0:

        assert reduction <= 1.0 and reduction > 0.0, 'reduction value must lie between 0.0 and 1.0'



    # check if upsampling_conv has minimum number of filters

    # minimum is set to 12, as at least 3 color channels are needed for correct upsampling



    # layers in each dense block

    if type(nb_layers_per_block) is list or type(nb_layers_per_block) is tuple:

        nb_layers = list(nb_layers_per_block)  # Convert tuple to list


        bottleneck_nb_layers = nb_layers[-1]

        rev_layers = nb_layers[::-1]

        nb_layers.extend(rev_layers[1:])

    else:

        bottleneck_nb_layers = nb_layers_per_block

        nb_layers = [nb_layers_per_block] * (2 * nb_dense_block + 1)



    # compute compression factor

    compression = 1.0 - reduction



    # Initial convolution

    x = Conv2D(init_conv_filters, (7, 7), kernel_initializer='he_normal', padding='same', name='initial_conv2D',

               use_bias=False, kernel_regularizer=l2(weight_decay))(img_input)

    x = BatchNormalization(axis=concat_axis, epsilon=1.1e-5)(x)

    x = Activation('relu')(x)



    nb_filter = init_conv_filters



    skip_list = []



    # Add dense blocks and transition down block

    for block_idx in range(nb_dense_block):

        x, nb_filter = __dense_block(x, nb_layers[block_idx], nb_filter, growth_rate, dropout_rate=dropout_rate,

                                     weight_decay=weight_decay)



        # Skip connection

        skip_list.append(x)



        # add transition_block

        x = __transition_block(x, nb_filter, compression=compression, weight_decay=weight_decay)



        nb_filter = int(nb_filter * compression)  # this is calculated inside transition_down_block



    # The last dense_block does not have a transition_down_block

    # return the concatenated feature maps without the concatenation of the input

    _, nb_filter, concat_list = __dense_block(x, bottleneck_nb_layers, nb_filter, growth_rate,

                                              dropout_rate=dropout_rate, weight_decay=weight_decay,

                                              return_concat_list=True)



    skip_list = skip_list[::-1]  # reverse the skip list



    # Add dense blocks and transition up block

    for block_idx in range(nb_dense_block):

        n_filters_keep = growth_rate * nb_layers[nb_dense_block + block_idx]



        # upsampling block must upsample only the feature maps (concat_list[1:]),

        # not the concatenation of the input with the feature maps (concat_list[0].

        l = concatenate(concat_list[1:], axis=concat_axis)



        t = __transition_up_block(l, nb_filters=n_filters_keep, type=upsampling_type, weight_decay=weight_decay)



        # concatenate the skip connection with the transition block

        x = concatenate([t, skip_list[block_idx]], axis=concat_axis)



        # Dont allow the feature map size to grow in upsampling dense blocks

        x_up, nb_filter, concat_list = __dense_block(x, nb_layers[nb_dense_block + block_idx + 1], nb_filter=growth_rate,

                                                     growth_rate=growth_rate, dropout_rate=dropout_rate,

                                                     weight_decay=weight_decay, return_concat_list=True,

                                                     grow_nb_filters=False)



    if include_top:

        x = Conv2D(nb_classes, (1, 1), activation='linear', padding='same', use_bias=False)(x_up)



        if K.image_data_format() == 'channels_first':

            channel, row, col = input_shape

        else:

            row, col, channel = input_shape



        x = Reshape((row * col, nb_classes))(x)

        x = Activation(activation)(x)

        x = Reshape((row, col, nb_classes))(x)

    else:

        x = x_up



    return x









if __name__ == '__main__':



    from keras.utils.vis_utils import plot_model

    #model = DenseNetFCN((32, 32, 3), growth_rate=16, nb_layers_per_block=[4, 5, 7, 10, 12, 15], upsampling_type='deconv')

    model = DenseNet((32, 32, 3), depth=100, nb_dense_block=3,

                     growth_rate=12, bottleneck=True, reduction=0.5, weights=None)

    model.summary()



    from keras.callbacks import ModelCheckpoint, TensorBoard

    #plot_model(model, 'test.png', show_shapes=True)