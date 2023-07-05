import os
import subprocess as sp
import zipfile
from pathlib import Path

import numpy as np


class Raw_Writer:
    """A class to write the raw frames from a Basler camera to a Numpy npz archive

    Temporarily saved the frames as separate files (in folder cam1_out) and creates the npz upon file closing

    Parameters
    -----------

    filename
      Any filename, should end with '.npz'
    """

    def __init__(self, filename: str) -> None:
        self.filename = filename
        self.tmpdir = filename[:-4]
        if not Path(self.tmpdir).is_dir():
            Path(self.tmpdir).mkdir()
        self.files = 0

    def write_frame(self, img_array, path="."):
        if not os.path.exists(f"{path}/{self.tmpdir}"):
            # if the demo_folder directory is not present
            # then create it.
            os.makedirs(f"{path}/{self.tmpdir}")
        tmpfilename = f"{path}/{self.tmpdir}/frame_{self.files}.npy"
        np.save(tmpfilename, img_array)
        self.files += 1

    def close(self):
        self.file = zipfile.ZipFile(
            self.filename, mode="w", compression=zipfile.ZIP_DEFLATED
        )
        for fnum in range(self.files):
            tmpfilename = f"{self.tmpdir}/frame_{fnum}.npy"
            self.file.write(tmpfilename)
            os.remove(tmpfilename)
        self.file.close()
        self.file = None


class FFMPEG_VideoWriter:
    """A class for FFMPEG-based video writing.

    From https://github.com/basler/pypylon/issues/113

    A class to write videos using ffmpeg. ffmpeg will write in a large
    choice of formats.

    Parameters
    -----------

    filename
      Any filename like 'video.mp4' etc. but if you want to avoid
      complications it is recommended to use the generic extension
      '.avi' for all your videos.

    size
      Size (width,height) of the output video in pixels.

    fps
      Frames per second in the output video file.

    codec
      FFMPEG codec. It seems that in terms of quality the hierarchy is
      'rawvideo' = 'png' > 'mpeg4' > 'libx264'
      'png' manages the same lossless quality as 'rawvideo' but yields
      smaller files. Type ``ffmpeg -codecs`` in a terminal to get a list
      of accepted codecs.

      Note for default 'libx264': by default the pixel format yuv420p
      is used. If the video dimensions are not both even (e.g. 720x405)
      another pixel format is used, and this can cause problem in some
      video readers.

    audiofile
      Optional: The name of an audio file that will be incorporated
      to the video.

    preset
      Sets the time that FFMPEG will take to compress the video. The slower,
      the better the compression rate. Possibilities are: ultrafast,superfast,
      veryfast, faster, fast, medium (default), slow, slower, veryslow,
      placebo.

    bitrate
      Only relevant for codecs which accept a bitrate. "5000k" offers
      nice results in general.

    withmask
      Boolean. Set to ``True`` if there is a mask in the video to be
      encoded.

    """

    def __init__(
        self,
        filename,
        size,
        fps,
        codec="png",
        audiofile=None,
        preset="medium",
        bitrate=None,
        pixfmt="bayer_rggb8",
        logfile=None,
        threads=None,
        ffmpeg_params=None,
    ):
        if logfile is None:
            logfile = sp.PIPE
        self.count = 0
        # self.proc = None
        self.filename = filename
        self.codec = codec
        self.ext = self.filename.split(".")[-1]
        # order is important
        self.cmd = [
            r"C:\Users\ARUNA\IR Labs\ffmpeg-6.0-essentials_build\ffmpeg-6.0-essentials_build\bin/ffmpeg",
            "-y",
            "-loglevel",
            "error" if logfile == sp.PIPE else "info",
            "-f",
            "rawvideo",
            "-vcodec",
            "rawvideo",
            "-s",
            "%dx%d" % (size[1], size[0]),
            "-pix_fmt",
            pixfmt,
            "-r",
            "%.02f" % fps,
            "-i",
            "-",
        ]
        self.cmd.extend(
            [
                "-vcodec",
                codec,
                "-preset",
                preset,
            ]
        )
        if ffmpeg_params is not None:
            self.cmd.extend(ffmpeg_params)
        if bitrate is not None:
            self.cmd.extend(["-b", bitrate])
        if threads is not None:
            self.cmd.extend(["-threads", str(threads)])

        self.cmd.extend([self.filename])

        self.popen_params = {"stdout": sp.DEVNULL, "stderr": logfile, "stdin": sp.PIPE}

        # This was added so that no extra unwanted window opens on windows
        # when the child process is created
        if os.name == "nt":
            self.popen_params["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

    def write_frame(self, img_array, file_loc):
        """Writes one frame in the file."""

        try:
            if file_loc is None:
                raise ValueError(
                    "File path is not set. Please specify the output video location."
                )

            # Create a new subprocess and add file location as the last element
            if self.count == 0:
                self.cmd.extend([file_loc + "/" + self.filename])

                self.proc = sp.Popen(self.cmd, **self.popen_params)

            # Check if the subprocess is still running before writing the frame
            if self.proc.poll() is None:
                self.proc.stdin.write(img_array.tobytes())
                self.count += 1
            else:
                print("Process has terminated.")

        except IOError as err:
            _, ffmpeg_error = self.proc.communicate()
            error = str(err) + (
                "\n\nMoviePy error: FFMPEG encountered "
                "the following error while writing file %s:"
                "\n\n %s" % (self.filename, str(ffmpeg_error))
            )

            if b"Unknown encoder" in ffmpeg_error:
                error = error + (
                    "\n\nThe video export "
                    "failed because FFMPEG didn't find the specified "
                    "codec for video encoding (%s). Please install "
                    "this codec or change the codec when calling "
                    "write_videofile. For instance:\n"
                    "  >>> clip.write_videofile('myvid.webm', codec='libvpx')"
                ) % (self.codec)

            elif b"incorrect codec parameters ?" in ffmpeg_error:
                error = error + (
                    "\n\nThe video export "
                    "failed, possibly because the codec specified for "
                    "the video (%s) is not compatible with the given "
                    "extension (%s). Please specify a valid 'codec' "
                    "argument in write_videofile. This would be 'libx264' "
                    "or 'mpeg4' for mp4, 'libtheora' for ogv, 'libvpx for webm. "
                    "Another possible reason is that the audio codec was not "
                    "compatible with the video codec. For instance the video "
                    "extensions 'ogv' and 'webm' only allow 'libvorbis' (default) as a"
                    "video codec."
                ) % (self.codec, self.ext)

            elif b"encoder setup failed" in ffmpeg_error:
                error = error + (
                    "\n\nThe video export "
                    "failed, possibly because the bitrate you specified "
                    "was too high or too low for the video codec."
                )

            elif b"Invalid encoder type" in ffmpeg_error:
                error = error + (
                    "\n\nThe video export failed because the codec "
                    "or file extension you provided is not a video"
                )

            raise IOError(error)

    def close(self):
        if self.proc:
            self.proc.stdin.close()
            if self.proc.stderr is not None:
                self.proc.stderr.close()
            self.proc.wait()

        self.proc = None

    # Support the Context Manager protocol, to ensure that resources are cleaned up.

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
