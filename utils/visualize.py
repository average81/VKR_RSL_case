import cv2
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
