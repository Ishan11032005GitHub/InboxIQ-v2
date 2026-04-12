# import kagglehub

# # Download latest version
# path = kagglehub.dataset_download("")

# print("Path to dataset files:", path)

import kagglehub
import shutil
import os

# Download dataset
path = kagglehub.dataset_download("beatoa/spamassassin-public-corpus")

print("Downloaded to:", path)
 
# Current folder (where script is running)
current_dir = os.getcwd()

# Copy dataset to current folder
destination = os.path.join(current_dir, "spamassassin_public_corpus")

if not os.path.exists(destination):
    shutil.copytree(path, destination)

print("Dataset copied to:", destination)