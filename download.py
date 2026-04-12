import kagglehub
import shutil
import os

# Download dataset
path = kagglehub.dataset_download("wcukierski/enron-email-dataset")

print("Downloaded to:", path)

# Current folder (where script is running)
current_dir = os.getcwd()

# Copy dataset to current folder
destination = os.path.join(current_dir, "enron_email_dataset")

if not os.path.exists(destination):
    shutil.copytree(path, destination)

print("Dataset copied to:", destination)