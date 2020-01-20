import cv2
import os, glob
import pydicom
import numpy as np
import torch
import torch.utils.data as data
from torchvision.transforms import Compose, ToTensor, Resize, Normalize, RandomHorizontalFlip, TenCrop
from torch.utils.data import DataLoader
from torchvision.transforms import transforms
#from matplotlib import pyplot as plt
# import sys
# sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../options')))
# from options import args
#need to add center crop!!
# 은별 : 요거 누가 쓴거지? center crop 추가하기는 했는데 사이즈가 애매하군
# 은별 : 흠 ... tencrop추가할까? 일단은 center crop해놨어용

#자연 : flip 좋은 생각 아닌거 같아, 우리가 detect하는것이 오른쪽/왼쪽이 정해져 있어서 편파적으로 학습하게 두는게 더 좋을것같은데 어때?
#은별 : 직관적으로 무슨 뜻인지 알겠는데, flip하는 일이 어려운일이 아니니까 직접해보고 결과를 비교하는게 가장 확실할 것 같아!


def dicom2png(dcm_pth):

#reference https://www.kaggle.com/gzuidhof/full-preprocessing-tutorial
#reference https://blog.kitware.com/dicom-rescale-intercept-rescale-slope-and-itk/
#reference https://opencv-python.readthedocs.io/en/latest/doc/20.imageHistogramEqualization/imageHistogramEqualization.html

    dc = pydicom.dcmread(dcm_pth)
    dc_arr = dc.pixel_array


    """자연
    HU(Hounsfield Units)에 맞게 pixel 값 조정
    """
    dc_arr = dc_arr.astype(np.int16)
    dc_arr[dc_arr == -2000] = 0
    #dc_arr = cv2.equalizeHist(dc_arr)


    intercept = dc.RescaleIntercept
    slope = dc.RescaleSlope

    if slope != 1:
        dc_arr = slope * dc_arr.astype(np.float64)
        dc_arr = dc_arr.astype(np.int16)

    dc_arr += np.int16(intercept)

    MIN_BOUND = -1000.0
    MAX_BOUND = 400.0

    dc_arr = 255.0 * (dc_arr - MIN_BOUND) / (MAX_BOUND - MIN_BOUND)
    dc_arr[dc_arr > 255.0] = 255.0
    dc_arr[dc_arr < 0.0] = 0.0
    H, W = dc_arr.shape
    dc_arr = dc_arr.reshape(H, W, 1)
    dc_arr = np.uint8(dc_arr)

    # 자연 : create a CLAHE(Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit = 1.0, tileGridSize = (8,8))
    nor_dc_arr = clahe.apply(dc_arr)
    nor_dc_arr = nor_dc_arr.reshape(1, H, W)

    # nor_dc_arr = np.array(nor_dc_arr/255.0, dtype = np.float)
    return nor_dc_arr




def mask_transform(opt):
    if opt.augmentation:
        compose = Compose([
            # transforms.Scale(opt.img_size),
            transforms.CenterCrop(224),
            #RandomHorizontalFlip(),
            # transforms.ToTensor(),
        ])
    else:
        compose = Compose([
            # transforms.Scale(opt.img_size),
            # transforms.ToTensor()
        ])

    return compose

def img_transform(opt):
    if opt.augmentation:
        compose = Compose([
            # transforms.Scale(opt.img_size),
            transforms.CenterCrop(224),
            #RandomHorizontalFlip(),
            # transforms.ToTensor(),
            """
            # Normalize or Histogram Equalization? choose 1

            transforms.Normalize([0.485, 0.456, 0.406],[0.229, 0.224, 0.225])
            """
        ])
    else:
        compose = Compose([
            # transforms.Scale(opt.img_size),
            # transforms.ToTensor()
        ])
        
    return compose

def normalize(img):

    max = img.max()
    min = img.min()
    img = (img-min)/(max-min)
    # print(img.dtype)

    return img

class DatasetFromFolder(data.Dataset):
    def __init__(self, opt):
        super(DatasetFromFolder, self).__init__()

        #ex) img_list = [1000000, 1000001,1000002,1000003,1000006,1000010,...]
        #예진: mode 사용하여 img_list를 train과 test하는 경우로 분리
        if opt.mode == 'train':
            self.img_list = os.listdir(opt.train_dir)
        else: #test
            #ex) img_list = [1000008.dcm, 10000010.dcm,...]
            self.img_list = os.listdir(opt.test_dir)

        self.train_dir = opt.train_dir
        self.test_dir = opt.test_dir
        self.opt = opt
        self.img_transform = img_transform(opt)
        self.mask_transform = mask_transform(opt)

    def __getitem__(self, idx):

        #예진: train/test 분리
        if self.opt.mode == 'train':
            # ex) img_list_path = '/data/train/1000000'
            # 채송: img_list ==> self.img_list로 메소드 정정
            img_list_path = os.path.join(self.train_dir + '/' + self.img_list[idx])
            # ex) img_files = ['100000.dcm','100000_AorticKnob.png','100000_Carina.png', ...] -> 1개의 dcm + 8개 mask
            img_files = os.listdir(img_list_path)
            masks = np.array([])
            
            for img in img_files:
                # print('\n\n',img)
                if '.dcm' in img:
                    # input_img : 0-1 histogram equalization 한 후
                    # input_img = dicom2png(os.path.join(img_list_path, img))
                    input_img = dicom2png(os.path.join(img_list_path, img))
                    c, H, W = input_img.shape #dicom2png에서 이미 1.h.w를 반환함
                    input_img = normalize(input_img)
                    # input_img = self.img_transform(input_img)
                    #input_img=input_img.transpose((2, 0, 1)) # HWC to CHW


                # else:  # .png
                # 채송: 확실하게 하기 위해 else 말고 elif .png 넣음
                elif '.png' in img:
                    # mask = cv2.imread(os.path.join(img_list_path, img))
                    # 채송: mask image가 그레이 스케일이지만 채널이 8비트인 컬러 이미지이기 때문에 GRAYSCALE로 읽음
                    mask = cv2.imread(os.path.join(img_list_path, img), cv2.IMREAD_GRAYSCALE)
                    #mask = mask.reshape(self.opt.num_class, H, W)
                    #mask = mask.reshape(self.opt.num_class, H, W)
                    mask = normalize(mask)
                    masks = np.append(masks, mask)

            background = np.zeros((H,W))
            masks = np.append(background, masks)
            masks.reshape(self.opt.num_class + 1, H, W)

            masks = masks.argmax(axis = 0)
            input_img = self.img_transform(input_img)

        
        else: #test
            img_list_path = os.path.join(self.test_dir, self.img_list[idx])
            if '.dcm' in img_list_path :
                # input_img : 0-1 histogram equalization 한 후
                # input_img = dicom2png(os.path.join(img_list_path, img))
                input_img = dicom2png(img_list_path)
                input_img = self.img_transform(input_img)
                input_img = normalize(input_img)
            masks = np.array([])

        return input_img, masks, img_list_path

    def __len__(self):
        return len(self.img_list)


def get_data_loader(opt):
    #train dataset만 오픈되어있지만 그래도 valid를 확인하고 싶으니깐 
    #train dataset을 train : valid = 8:2 로 나누는 코드

    dataset = DatasetFromFolder(opt)

    train_len = int(opt.train_ratio * len(dataset))
    valid_len = int(len(dataset) - train_len)

    train_dataset, valid_dataset = data.random_split(dataset, lengths = [train_len, valid_len])

    train_data_loader = DataLoader(dataset = train_dataset, 
                                    batch_size = opt.batch_size,
                                    shuffle = True)
    valid_data_loader = DataLoader(dataset = valid_dataset,
                                    batch_size = opt.batch_size,
                                    shuffle = False)

    return train_data_loader, valid_data_loader


#자연: valid 생성 안할 때 train_data_loader
#예진: test_data_loader로 사용

def get_test_data_loader(opt):
    
    dataset = DatasetFromFolder(opt)

    test_data_loader = DataLoader(dataset = dataset, 
                                    batch_size = opt.batch_size,
                                    shuffle = False)

    return test_data_loader