import torchvision.datasets.video_utils

from torchvision.datasets.video_utils import VideoClips
from torchvision.datasets.utils import list_dir
from torchvision.datasets.folder import make_dataset
from torchvision.datasets.vision import VisionDataset
from torchvision.utils import save_image
from torchvision.transforms.functional import to_tensor
from PIL import Image
from torch import Tensor
import torch
from .kinetics import Kinetics400
from pathlib import Path
from data.saliency.methods import gbvs_from_video, itti_from_frame
from typing import Tuple, List

import numpy as np

class SalientKinetics400(Kinetics400):
    """
    Args:
        root (string): Root directory of the Kinetics-400 Dataset.
        frames_per_clip (int): number of frames in a clip
        step_between_clips (int): number of frames between each clip
        transform (callable, optional): A function/transform that  takes in a TxHxWxC video
            and returns a transformed version.

    Returns:
        video (Tensor[T, H, W, C]): the `T` video frames
        audio(Tensor[K, L]): the audio frames, where `K` is the number of channels
            and `L` is the number of points
        label (int): class of the video clip
    """

    def __init__(self, root, salient_root, frames_per_clip, step_between_clips=1, frame_rate=None,
                 extensions=('mp4',), transform=None, salient_transform=None, 
                 cached=None, _precomputed_metadata=None):
        super(SalientKinetics400, self).__init__(root, frames_per_clip, 
                                                step_between_clips=step_between_clips,
                                                frame_rate=frame_rate, extensions=extensions, 
                                                transform=transform, cached=cached, 
                                                _precomputed_metadata=_precomputed_metadata)

        self.salient_transform = salient_transform
        self.salient_root = Path(salient_root)
        if not self.salient_root.is_dir():
            # No salient cache available, create new one
            self.salient_root.mkdir()
         
    def init_from_cache(self):
        """
        Initializes saliency_maps from existing cache.
        """
#        for video_dir in self.salient_root:
#            pass

        return {}

    def generate_saliency(self, video: Tensor):
        """Generate saliency map for given video clip, will overwrite if 
        files already exist.

        Args:
            video (Tensor): The video from which to generate saliency maps.
            idx (int): Index into the VideoClip object from Kinetics400 dataset.
        """
        # TODO: logic for switching method
        # saliency = gbvs_from_video(video)
        saliency = itti_from_frame(video)


        return saliency

    def clip_idx_to_frame(self, clip_location: Tuple[int, int]) -> List:
        video_idx, clip_idx = clip_location

        video_pts = self.video_clips.metadata['video_pts'][video_idx]
        clip_pts = self.video_clips.clips[video_idx][clip_idx]

        # Find specific frame
        # clip_length = clip.shape[0]
        # start_frame = (clip_idx - 1) * clip_length
        # frame_idx = video_pts == clip_pts[0]
        # assert start_frame == frame_idx.nonzero(as_tuple=True)[0]
        
        # Map video_pts values to indices, theses indices are the frame ids
        to_frame = { pts.item(): i for i, pts in enumerate(video_pts) }
        frames = [to_frame[pts.item()] for pts in clip_pts]
        return frames

    def load_frame(self, path: Path) -> Tensor:
        with open(str(path), 'rb') as f:
            img = Image.open(f)
            img = img.convert('L')
        img = to_tensor(img)
        # Color channel is the last dimension
        img = img.permute(1, 2, 0)
        return img

    def get_saliency_clip(self, clip: Tensor, clip_location: Tuple[int, int]) -> Tensor:
        """
        Get (precomputed) saliency clip
        """
        video_idx, clip_idx = clip_location

        video_path = self.video_clips.metadata['video_paths'][video_idx]
        
        frames = self.clip_idx_to_frame(clip_location)
        
        video_name = Path(video_path).stem

        saliencies = []
        for frame_in_clip, frame in enumerate(frames):
            cached_path = self.salient_root / video_name / f'{frame}.png'

            if cached_path.is_file():
                saliency_frame = self.load_frame(cached_path)
                print(saliency_frame.shape, 'load_frame shape')
            else:
                print(f'Generating saliency for video {video_name} frame {frame}')
                saliency_frame = self.generate_saliency(clip[frame_in_clip])

                if not (self.salient_root / video_name).is_dir():
                    (self.salient_root / video_name).mkdir()
                 
                save_image(saliency_frame, cached_path, normalize=True)

            saliencies.append(saliency_frame.byte())

        return torch.stack(saliencies)


    def __getitem__(self, idx):
        success = False
        while not success:
            try:
                video, audio, info, video_idx = self.video_clips.get_clip(idx)

                # This information is needed for saliency caching
                clip_location = self.video_clips.get_clip_location(idx)
                # saliency = self.get_saliency_clip(video, clip_location)
                success = True
            except:
                print('skipped idx', idx)
                idx = np.random.randint(self.__len__())
        
        saliency = self.get_saliency_clip(video, clip_location)
        label = self.samples[video_idx][1]
        if self.transform is not None:
            print('vid', video.dtype, video.shape)
            video = self.transform(video)

        if self.salient_transform is not None:
            print('sal', saliency.dtype, saliency.shape)
            saliency = self.salient_transform(saliency)

        return video, audio, saliency, label
