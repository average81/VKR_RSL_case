import cv2
import matplotlib.pyplot as plt
#Визуализация дефектов
def visualize_defects(image, pascal_voc):
    img2 = image.copy()
    for item in pascal_voc["annotation"]["objects"]:
        xmin = int(item["bndbox"]["xmin"])
        ymax = int(item["bndbox"]["ymax"])
        xmax = int(item["bndbox"]["xmax"])
        ymin = int(item["bndbox"]["ymin"])
        if item["name"] == "ellipse":
            cv2.rectangle(img2, (xmin, ymin), (xmax, ymax), (0, 255, 0), 2)
        else:
            cv2.rectangle(img2, (xmin, ymin), (xmax, ymax), (0, 0, 255), 2)
    return img2

def draw_roc_curve(fpr, tpr, thresholds):
    if fpr is not None and tpr is not None:
        plt.plot(fpr, tpr, label='ROC curve')
        plt.plot([0, 1], [0, 1], 'k--', label='Random guess')
        plt.xlabel('False Positive Rate')
        plt.ylabel('True Positive Rate')
        plt.title('ROC Curve')
        """if thresholds is not None:
            for i in range(len(thresholds)):
                plt.annotate(f'{thresholds[i]:.3f}', (fpr[i], tpr[i]), textcoords="offset points", xytext=(0,10), ha='center')"""
        plt.legend()
        plt.show()