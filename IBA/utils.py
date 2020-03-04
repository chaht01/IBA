import numpy as np
from skimage.transform import resize


# this module should be independent of torch and tensorflow
assert 'torch' not in globals()
assert 'tf' not in globals()
assert 'tensorflow' not in globals()


class WelfordEstimator:
    """
    Estimates the mean and standard derivation.
    For the algorithm see ``https://en.wikipedia.org/wiki/Algorithms_for_calculating_variance``.
    Args:
        channels: The number of channels of the feature map
        height: The heigth of the feature map
        width: The width of the feature map
    Example:
        Given a batch of images ``imgs`` with shape ``(10, 3, 64, 64)``, the mean and std could
        be estimated as follows::
            imgs = torch.randn(10, 3, 64, 64)
            estim = WelfordEstimator(3, 64, 64)
            estim(imgs)
            # returns the estimated mean
            estim.mean()
            # returns the estimated std
            estim.std()
            # returns the number of samples, here 10
            estim.n_samples()
            # returns a mask with active neurons
            estim.active_neurons()
    """
    def __init__(self):
        super().__init__()
        self.m = None
        self.s = None
        self._n_samples = 0
        self._neuron_nonzero = None

    def fit(self, x):
        """ Update estimates without altering x """
        if self._n_samples == 0:
            # Initialize on first datapoint
            shape = x.shape[1:]
            self.m = np.zeros(shape)
            self.s = np.zeros(shape)
            self._neuron_nonzero = np.zeros(shape, dtype='long')
        for xi in x:
            self._neuron_nonzero += (xi != 0.)
            old_m = self.m.copy()
            self.m = self.m + (xi-self.m) / (self._n_samples + 1)
            self.s = self.s + (xi-self.m) * (xi-old_m)
            self._n_samples += 1
        return x

    def n_samples(self):
        """ Returns the number of seen samples. """
        return self._n_samples

    def mean(self):
        """ Returns the estimate of the mean. """
        return self.m

    def std(self):
        """returns the estimate of the standard derivation."""
        return np.sqrt(self.s / (self._n_samples - 1))

    def active_neurons(self, threshold=0.01):
        """
        Returns a mask of all active neurons.
        A neuron is considered active if ``n_nonzero / n_samples  > threshold``
        """
        return (self._neuron_nonzero.astype(np.float32) / self._n_samples) > threshold

    def state_dict(self):
        return {
            'm': self.m,
            's': self.s,
            'n_samples': self._n_samples,
            'neuron_nonzero': self._neuron_nonzero,
        }

    def load_state_dict(self, state):
        self.m = state['m']
        self.s = state['s']
        self._n_samples = state['n_samples']
        self._neuron_nonzero = state['neuron_nonzero']


def to_saliency_map(capacity, shape=None, data_format='NCHW'):
    """
    Converts the layer capacity (in nats) to a saliency map (in bits) of the given shape .
    """
    if data_format == 'NCHW':
        saliency_map = np.nansum(capacity, 0)
    if data_format == 'NHWC':
        saliency_map = np.nansum(capacity, -1)

    # to bits
    saliency_map /= float(np.log(2))

    if shape is not None:
        ho, wo = saliency_map.shape
        h, w = shape
        # Scale bits to the pixels
        saliency_map *= (ho*wo) / (h*w)
        return resize(saliency_map, shape, order=1, preserve_range=True)
    else:
        return saliency_map


def plot_saliency_map(saliency_map, img=None, ax=None, label='Bits / Pixel',
                      min_alpha=0.2, max_alpha=0.7, vmax=None,
                      colorbar_size=0.3, colorbar_pad=0.08):
    """
    Plots the heatmap with an bits/pixel colorbar and optionally overlays the image.

    Args:
        saliency_map: np.ndarray the saliency_map
        img: np.ndarray show this image under the saliency_map
        ax: matplotlib axis. If ``None``, a new plot is created
        label: label for the colorbar
        min_alpha: minimum alpha value for the overlay. only used if ``img`` is given
        max_alpha: maximum alpha value for the overlay. only used if ``img`` is given
        vmax: maximum value for colorbar
        colorbar_size: width of the colorbar. default: Fixed(0.3)
        colorbar_pad: width of the colorbar. default: Fixed(0.08)

    Returns:
        The matplotlib axis ``ax``.
    """
    import matplotlib as mpl
    import matplotlib.pyplot as plt
    from mpl_toolkits.axes_grid1.axes_divider import make_axes_locatable
    from mpl_toolkits.axes_grid1.axes_size import Fixed
    if ax is None:
        fig, ax = plt.subplots(1, 1, figsize=(5.5, 4.0))

    if img is not None:
        # Underlay the image as greyscale
        grey = img.mean(2)
        ax.imshow(np.stack((grey, grey, grey), axis=2))

    ax1_divider = make_axes_locatable(ax)
    if type(colorbar_size) == float:
        colorbar_size = Fixed(colorbar_size)
    if type(colorbar_pad) == float:
        colorbar_pad = Fixed(colorbar_pad)
    cax1 = ax1_divider.append_axes("right", size=colorbar_size, pad=colorbar_pad)
    if vmax is None:
        vmax = saliency_map.max()
    norm = mpl.colors.Normalize(vmin=0, vmax=vmax)
    n = 256
    half_jet_rgba = plt.cm.seismic(np.linspace(0.5, 1, n))
    half_jet_rgba[:, -1] = np.linspace(0.2, 1, n)
    cmap = mpl.colors.ListedColormap(half_jet_rgba)
    hmap_jet = cmap(norm(saliency_map))
    if img is not None:
        hmap_jet[:, :, -1] = (max_alpha - min_alpha)*norm(saliency_map) + min_alpha
    ax.imshow(hmap_jet, alpha=1.)
    cbar = mpl.colorbar.ColorbarBase(cax1, cmap=cmap, norm=norm)
    cbar.set_label(label, fontsize=16)

    ax.set_xticks([])
    ax.set_yticks([])
    ax.grid('off')
    ax.set_frame_on(False)
    return ax
