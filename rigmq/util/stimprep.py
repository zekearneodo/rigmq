from scipy.io import wavfile
from scipy.signal import resample

import numpy as np
import os
import logging
import json

logger = logging.getLogger('rigmq.util.stimprep')

def normalize(x: np.array, max_amp: np.float=0.9)-> np.array:
    y = x.astype(np.float)
    y = y - np.mean(y)
    y = y / np.max(np.abs(y)) # if it is still of-centered, scale to avoid clipping in the widest varyng sign
    return y * max_amp

def fill_int_range(x: np.array, dtype: np.dtype):
    min_int = np.iinfo(dtype).min
    max_int = np.iinfo(dtype).max

    if min_int==0: # for unsigned types shift everything
        x = x + np.min(x)
    y = x * max_int
    return y.astype(dtype)

def make_stereo_stim(wave_in, out_sf, tag_freq=1000):
    in_sf, data = wavfile.read(wave_in)
    d_type = data.dtype
    logger.debug('File sampling rate {}'.format(in_sf))
    
    # make all the resample in floats [-0.9; 0.9]
    float_data = normalize(data, max_amp=0.9)
    if int(in_sf) == int(out_sf):
        song = float_data
        new_len = float_data.shape[0]
    else:
        curr_len = float_data.shape[0]
        new_len = int(curr_len * out_sf / in_sf)
        logger.info('Will resample from {} to {} sampes'.format(curr_len, new_len))
        song = resample(float_data, new_len)
    # make the tags in floats too
    tag = np.sin(2 * np.pi * tag_freq * np.arange(new_len) / out_sf) * 0.9
    
    [song_out, tag_out] = [fill_int_range(z, d_type) for z in [song, tag]]
    return np.column_stack([song_out, tag_out])


def create_sbc_stim(file_list, location_fold, out_s_f, stim_tag_dict=None):
    out_dir = os.path.join(location_fold, 'sbc_stim')
    os.makedirs(out_dir, exist_ok=True)
    for stim_f_name in file_list:
        stim_name = stim_f_name.split('.')[0]
        wave_in = os.path.join(location_fold, '{}.wav'.format(stim_name))
        logger.info('Processing {}'.format(wave_in))
        if stim_tag_dict:
            tag_freq = stim_tag_dict[stim_name]
            logger.info('tag_freq = {}'.format(tag_freq))
            song_out = make_stereo_stim(wave_in, out_s_f, tag_freq=tag_freq)
        else:
            song_out = make_stereo_stim(wave_in, out_s_f)
        wave_out = os.path.join(out_dir, '{}_tag.wav'.format(stim_name))
        wavfile.write(wave_out, out_s_f, song_out)
        logger.info('Saved to {}'.format(wave_out))

    tags_par_file = os.path.join(out_dir, 'stim_tags.json')
    with open(tags_par_file, 'w') as outfile:
        json.dump(stim_tag_dict, outfile)
    logger.info('Saved tags .json file to {}'.format(tags_par_file))