import os
import random
import cv2
import numpy as np
import torch
import torch.nn as nn
import torchvision.transforms as transforms
from torchvision import models
from sklearn.metrics.pairwise import cosine_similarity
from torch.utils.data import Dataset, DataLoader


def generate_random_regions(
    image_shape, num_regions, region_shape="rectangular", seed=None
):
    if seed is not None:
        random.seed(seed)
    regions = []
    height, width = image_shape[:2]
    for _ in range(num_regions):
        if region_shape == "rectangular":
            x1 = random.randint(0, width - 50)
            y1 = random.randint(0, height - 50)
            x2 = random.randint(x1 + 50, min(x1 + 200, width))
            y2 = random.randint(y1 + 50, min(y1 + 200, height))
            regions.append((x1, y1, x2, y2))
    return regions


def extract_regions(image, regions, region_shape="rectangular"):
    region_images = []
    for region in regions:
        if region_shape == "rectangular":
            x1, y1, x2, y2 = region
            roi = image[y1:y2, x1:x2]
            region_images.append(roi)
    return region_images


preprocess = transforms.Compose(
    [
        transforms.ToPILImage(),
        transforms.Resize((224, 224)),
        transforms.ToTensor(),
        transforms.Normalize(mean=[0.485, 0.456, 0.406], std=[0.229, 0.224, 0.225]),
    ]
)


class FeatureExtractor(nn.Module):
    def __init__(self, model):
        super(FeatureExtractor, self).__init__()
        self.features = model.features
        self.avgpool = model.avgpool
        self.flatten = nn.Flatten()
        self.fc = nn.Sequential(*list(model.classifier[:4]))

    def forward(self, x):
        x = self.features(x)
        x = self.avgpool(x)
        x = self.flatten(x)
        x = self.fc(x)
        return x


def extract_features(region_image, model, device):
    if region_image.size == 0:
        return np.zeros((4096,))
    try:
        input_tensor = preprocess(region_image)
        input_batch = input_tensor.unsqueeze(0).to(device)
        with torch.no_grad():
            features = model(input_batch)
        features = features.cpu().numpy().flatten()
        return features
    except Exception as e:
        print(f"Error extracting features: {e}")
        return np.zeros((4096,))


def process_image(image_path, regions, model, device):
    image = cv2.imread(image_path)
    if image is None:
        print(f"Error: Unable to load image at {image_path}")
        return None
    region_images = extract_regions(image, regions)
    features_list = []
    for region_image in region_images:
        features = extract_features(region_image, model, device)
        features_list.append(features)
    return features_list


def compute_similarity(features_list1, features_list2):
    similarities = []
    for feat1, feat2 in zip(features_list1, features_list2):
        sim = cosine_similarity([feat1], [feat2])[0][0]
        similarities.append(sim)
    return similarities


class HandwritingDataset(Dataset):
    def __init__(self, image_paths, labels, transform=None):
        self.image_paths = image_paths
        self.labels = labels
        self.transform = transform

    def __len__(self):
        return len(self.image_paths)

    def __getitem__(self, idx):
        image = cv2.imread(self.image_paths[idx])
        if image is None:
            raise ValueError(f"Error loading image {self.image_paths[idx]}")
        if self.transform:
            image = self.transform(image)
        label = self.labels[idx]
        return image, label


def main():
    image_path1 = "/Users/suryavirkapur/Projekts/plgrzr/data/plgrzr_output/prz_0aczijb4/prz_0aczijb4_1.jpg"
    image_path2 = "/Users/suryavirkapur/Projekts/plgrzr/data/plgrzr_output/prz_0bqz4iao/prz_0bqz4iao_1.jpg"
    num_regions = 10
    region_shape = "rectangular"
    seed = 42

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")

    image1 = cv2.imread(image_path1)
    image2 = cv2.imread(image_path2)

    if image1 is None or image2 is None:
        print("Error: One or both images could not be loaded.")
        return

    regions = generate_random_regions(
        image1.shape, num_regions, region_shape=region_shape, seed=seed
    )

    model = models.vgg16(pretrained=True)
    for param in model.features.parameters():
        param.requires_grad = False
    num_classes = 10
    model.classifier[6] = nn.Linear(4096, num_classes)
    model = model.to(device)

    feature_extractor = FeatureExtractor(model)
    feature_extractor.eval()
    feature_extractor.to(device)

    features_list1 = process_image(image_path1, regions, feature_extractor, device)
    features_list2 = process_image(image_path2, regions, feature_extractor, device)

    if features_list1 is None or features_list2 is None:
        print("Feature extraction failed.")
        return

    similarities = compute_similarity(features_list1, features_list2)
    overall_similarity = np.mean(similarities)
    print(f"Overall similarity: {overall_similarity:.4f}")


if __name__ == "__main__":
    main()
