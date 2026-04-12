import urllib.request
import os

URL = "https://www.cs.cmu.edu/~enron/enron_mail_20150507.tar.gz"
DOWNLOAD_FILE = "enron.tar.gz"

def download():
    if os.path.exists(DOWNLOAD_FILE):
        print("Dataset already downloaded.")
        return

    print("Downloading Enron dataset (~400MB)...")

    try:
        urllib.request.urlretrieve(URL, DOWNLOAD_FILE)
        print("Download completed.")
    except Exception as e:
        print("Download failed:", e)

if __name__ == "__main__":
    download()