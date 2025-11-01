import os
import re

import ants
import matplotlib.pyplot as plt

from utils.qc import ImageParam


def transform(prefix, fx, mv, tfm, interpolator='linear', qc_filename=None, clobber=False):
    print('\tTransforming')
    print('\t\tFixed', fx)
    print('\t\tMoving', mv)
    print('\t\tTransformations:', tfm)
    print('\t\tQC:', qc_filename)
    print()

    out_fn = prefix + re.sub('.nii.gz', '_rsl.nii.gz', os.path.basename(mv))
    if not os.path.exists(out_fn) or clobber:
        img_rsl = ants.apply_transforms(fixed=ants.image_read(fx),
                                        moving=ants.image_read(mv),
                                        transformlist=tfm,
                                        interpolator=interpolator,
                                        verbose=True
                                        )
        ants.image_write(img_rsl, out_fn)

        if type(qc_filename) == str:
            ImageParam(fx, qc_filename, out_fn, duration=600, nframes=15, dpi=200, alpha=[0.4]).volume2gif()
    return out_fn


def align(fx, mv, transform_method='SyNAggro', init=[], outprefix='', qc_filename=None):
    warpedmovout = outprefix + 'fwd.nii.gz'
    warpedfixout = outprefix + 'inv.nii.gz'
    fwdtransforms = outprefix + 'Composite.h5'
    invtransforms = outprefix + 'InverseComposite.h5'

    print(f'\tAligning\n\t\tFixed: {fx}\n\t\tMoving: {mv}\n\t\tTransform: {transform_method}')
    print(f'\t\tQC: {qc_filename}\n')
    output_files = warpedmovout, warpedfixout, fwdtransforms, invtransforms
    if False in [os.path.exists(fn) for fn in output_files]:
        out = ants.registration(fixed=ants.image_read(fx),
                                moving=ants.image_read(mv),
                                type_of_transform=transform_method,
                                init=init,
                                verbose=True,
                                outprefix=outprefix,
                                write_composite_transform=True
                                )
        ants.image_write(out['warpedmovout'], warpedmovout)
        ants.image_write(out['warpedfixout'], warpedfixout)

        if type(qc_filename) == str:
            ImageParam(fx, qc_filename, warpedmovout, duration=600, nframes=15, dpi=200, alpha=[0.3], edge_2=1,
                       cmap1=plt.cm.Greys, cmap2=plt.cm.Reds).volume2gif()

    return output_files