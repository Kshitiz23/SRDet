""" This code compares the pre and post prediction value of the objects pre and post of reconstructing a low-resolution image as an input to the detector"""


import numpy as np
from tensorflow.keras.models import Model, load_model, Sequential
from tensorflow.keras.applications.vgg16 import VGG16, preprocess_input, decode_predictions
from tensorflow.keras.applications import VGG16
from tensorflow.keras.preprocessing import image
from keras.layers import Input, Lambda, Activation, Conv2D, MaxPooling2D, ZeroPadding2D, Reshape, Concatenate

import struct
import numpy as np
from keras.layers import Conv2D
from keras.layers import Input
from keras.layers import BatchNormalization
from keras.layers import LeakyReLU
from keras.layers import ZeroPadding2D
from keras.layers import UpSampling2D
from keras.layers.merge import add, concatenate
from keras.models import Model
import tensorflow as tf

from numpy import expand_dims
from keras.models import load_model
from keras.preprocessing.image import load_img
from keras.preprocessing.image import img_to_array
from matplotlib import pyplot
from matplotlib.patches import Rectangle
from keras.preprocessing import image
from tensorflow.keras.applications.vgg16 import preprocess_input




#Labels for COCO that has CAR and Pedestrian as object
labels = ["person", "bicycle", "car", "motorbike", "aeroplane", "bus", "train", "truck",
"boat", "traffic light", "fire hydrant", "stop sign", "parking meter", "bench",
"bird", "cat", "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe",
"backpack", "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard",
"sports ball", "kite", "baseball bat", "baseball glove", "skateboard", "surfboard",
"tennis racket", "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana",
"apple", "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
"Chair", "Couch", "pottedplant", "Bed", "diningtable", "toilet", "TV", "laptop", "mouse",
"remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink", "refrigerator",
"book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"]
# define the expected input shape for the model
input_w, input_h = 416, 416


_MODEL_YOLO = ""
_MODEL_RETINANET = ""



# Functions neccesary to output a bounding box with prediction 
class BoundBox:
        def __init__(self, xmin, ymin, xmax, ymax, objness = None, classes = None):
                self.xmin = xmin
                self.ymin = ymin
                self.xmax = xmax
                self.ymax = ymax
                self.objness = objness
                self.classes = classes
                self.label = -1
                self.score = -1

        def get_label(self):
                if self.label == -1:
                        self.label = np.argmax(self.classes)

                return self.label

        def get_score(self):
                if self.score == -1:
                        self.score = self.classes[self.get_label()]

                return self.score
def _sigmoid(x):
        return 1. / (1. + np.exp(-x))

def decode_netout(netout, anchors, obj_thresh, net_h, net_w):
        grid_h, grid_w = netout.shape[:2]
        nb_box = 3
        netout = netout.reshape((grid_h, grid_w, nb_box, -1))
        nb_class = netout.shape[-1] - 5
        boxes = []
        netout[..., :2]  = _sigmoid(netout[..., :2])
        netout[..., 4:]  = _sigmoid(netout[..., 4:])
        netout[..., 5:]  = netout[..., 4][..., np.newaxis] * netout[..., 5:]
        netout[..., 5:] *= netout[..., 5:] > obj_thresh

        for i in range(grid_h*grid_w):
                row = i / grid_w
                col = i % grid_w
                for b in range(nb_box):
                        # 4th element is objectness score
                        objectness = netout[int(row)][int(col)][b][4]
                        if(objectness.all() <= obj_thresh): continue
                        # first 4 elements are x, y, w, and h
                        x, y, w, h = netout[int(row)][int(col)][b][:4]
                        x = (col + x) / grid_w # center position, unit: image width
                        y = (row + y) / grid_h # center position, unit: image height
                        w = anchors[2 * b + 0] * np.exp(w) / net_w # unit: image width
                        h = anchors[2 * b + 1] * np.exp(h) / net_h # unit: image height
                        # last elements are class probabilities
                        classes = netout[int(row)][col][b][5:]
                        box = BoundBox(x-w/2, y-h/2, x+w/2, y+h/2, objectness, classes)
                        boxes.append(box)
        return boxes
def _interval_overlap(interval_a, interval_b):
        x1, x2 = interval_a
        x3, x4 = interval_b
        if x3 < x1:
                if x4 < x1:
                        return 0
                else:
                     	return min(x2,x4) - x1
        else:
             	if x2 < x3:
                         return 0
                else:
                     	return min(x2,x4) - x3

def bbox_iou(box1, box2):
        intersect_w = _interval_overlap([box1.xmin, box1.xmax], [box2.xmin, box2.xmax])
        intersect_h = _interval_overlap([box1.ymin, box1.ymax], [box2.ymin, box2.ymax])
        intersect = intersect_w * intersect_h
        w1, h1 = box1.xmax-box1.xmin, box1.ymax-box1.ymin
        w2, h2 = box2.xmax-box2.xmin, box2.ymax-box2.ymin
        union = w1*h1 + w2*h2 - intersect
        return intersect/(union+0.00000001)
def do_nms(boxes, nms_thresh):
        if len(boxes) > 0:
                nb_class = len(boxes[0].classes)
        else:
             	return
        for c in range(nb_class):
                sorted_indices = np.argsort([-box.classes[c] for box in boxes])
                for i in range(len(sorted_indices)):
                        index_i = sorted_indices[i]
                        if boxes[index_i].classes[c] == 0: continue
                        for j in range(i+1, len(sorted_indices)):
                                index_j = sorted_indices[j]
                                if bbox_iou(boxes[index_i], boxes[index_j]) >= nms_thresh:
                                        boxes[index_j].classes[c] = 0
                                        
def load_image_pixels(filename, shape):
        # load the image to get its shape
        image = load_img(filename)
        width, height = image.size
        # load the image with the required size
        image = load_img(filename, target_size=shape)
        # convert to numpy array
        image = img_to_array(image)
        # scale pixel values to [0, 1]
        image = image.astype('float32')
        image /= 255.0
        # add a dimension so that we have one sample
        image = expand_dims(image, 0)
        return image, width, height
    
    
# draw all results
def draw_boxes(filename, v_boxes, v_labels, v_scores):
        # load the image
        data = pyplot.imread(filename)
        # plot the image
        pyplot.imshow(data)
        # get the context for drawing boxes
        ax = pyplot.gca()
        # plot each box
        for i in range(len(v_boxes)):
                box = v_boxes[i]
                # get coordinates
                y1, x1, y2, x2 = box.ymin, box.xmin, box.ymax, box.xmax
                # calculate width and height of the box
                width, height = x2 - x1, y2 - y1
                # create the shape
                rect = Rectangle((x1, y1), width, height, fill=False, color='white')
                # draw the box
                ax.add_patch(rect)
                # draw text and score in top left corner
                label = "%s (%.3f)" % (v_labels[i], v_scores[i])
                pyplot.text(x1, y1, label, color='white')
        # show the plot
        pyplot.show()
    


def main():
    img = 
    model = load_model('/home/tug87582/work/project_src/Detectors/YOLOV3/model_coco.h5')
    image = load_image_array("")
    yhat = model_boost.predict(image)

    for th in all_threshold:
        thres = th
        fp = open(os.path.join(_OBJECT_RESULTS,str(th),str(temp_item[0])+"_"+str(probs[0][related_objects[objectIndex][1]])+".txt"),'w')
        # summarize the shape of the list of arrays
        # define the anchors
        boxes = list()
        temp_meta_label = []
        for i in range(len(yhat)):
        # decode the output of the network
            boxes += decode_netout(yhat[i][0], anchors[i], class_threshold, input_w, input_h)
            # correct the sizes of the bounding boxes for the shape of the image
            correct_yolo_boxes(boxes, image_h, image_w, input_h, input_w)
            # suppress non-maximal boxes
            do_nms(boxes, 0.5)
            # define the labels
            # get the details of the detected objects
            v_boxes, v_labels, v_scores = get_boxes(boxes, labels, class_threshold)
            # summarize what we found
            print(v_labels)
            print("")
        draw_boxes(path1, v_boxes, v_labels, v_scores)

main()
