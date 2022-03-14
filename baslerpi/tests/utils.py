import urllib.request
import progressbar

BIGBUCKBUNNY_WEB = "http://commondatastorage.googleapis.com/gtv-videos-bucket/sample/BigBuckBunny.mp4"

pbar = None

def show_progress(block_num, block_size, total_size):
    global pbar
    if pbar is None:
        pbar = progressbar.ProgressBar(maxval=total_size)
        pbar.start()

    downloaded = block_num * block_size
    if downloaded < total_size:
        pbar.update(downloaded)
    else:
        pbar.finish()
        pbar = None


def download_file(resource=None, destination=None):
    if resource is None:
        resource = BIGBUCKBUNNY_WEB

    if destination is None:
        raise Exception("Provide destination path")

    print(f"Downloading {resource} -> {destination}")
    urllib.request.urlretrieve(resource, destination, show_progress)
