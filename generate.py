import logging as logger
import os
import shutil
import datetime
import random
import numpy as np
from PIL import Image, ImageDraw, ImageFont
import json
from skimage import io, feature
from createvoc import VocCreator


TEXT_LENGTH_MAX = 20
WIDTH_MAX = 5000 
HEIGHT_MAX = 5000
OFFSET_X_MAX = 50
OFFSET_Y_MAX = 50

def loadBGFile(res, cfg):
    # load all bg file
    res['bg'] = {}
    for root, dirnames, filenames in os.walk(cfg['BGPath']):
        for filename in filenames:
            fullname = os.path.join(root,filename)
            if filename.endswith(('.jpg','.jpeg','.gif','.png')):
                im = Image.open(fullname)
                res['bg'][fullname] = im
            else:
                print "FOUND Invalid bg file:%s"%(fullname)
    # load pure color bg file
    for color in [(188,188,188), (255,255,255)]:
        im = Image.new('RGB', (2000,2000), color = color)
        res['bg'][str(color)] = im

def loadFontFile(res, cfg):
    res['font'] = {}
    for fn in cfg['FontFiles']:
        for size in cfg['FontSizes']:
            font = ImageFont.truetype(fn, size)
            res['font'][fn] = font

def loadCharRange(res, cfg):
#    res['char'] = []
#    for c in cfg['Chars']:
#        assert c.isalnum()
    res['char'] = cfg['Chars']

def loadNoise(res, cfg):
    res['noise'] = cfg['NoiseText']

# get area color and return a reverse color
def getColor(im,x0,y0,w,h):
    #print "getColor(%d,%d,%d,%d)"%(x0,y0,x0+w,y0+h)
    data = np.array(im).astype(float)
    x1 = w+x0
    # only caculate 20 lines area
    if h>20:
        y1 = y0+20
    else:
        y1 = h+y0
    #print "area(%d,%d,%d,%d)"%(x0,y0,x1,y1)
    area = data[y0:y1,x0:x1].reshape((y1-y0)*(x1-x0),3)
    average = reduce(lambda p1,p2:(p1+p2)/2, area)
    def rev(c):
        if(128>=c>=64):
            return 255
        elif(192>=c>128):
            return 0
        else:
            return abs(255-c)
    r,g,b = average.astype(np.uint8)
    return tuple(map(lambda c:rev(c), [r,g,b]))


def addText(x0,y0,w0,h0,res,im,text='',ftName='',drawBox=False, randPos=True, color=''):
    #print "Start to addText:%s(%d,%d,%d,%d)"%(text,x0,y0,w0+x0,h0+x0)
    # Return total size of text: (width, heigh)
    xTotal,yTotal = 0,0
    # Return boxes include each tag
    # boxes is: {tag:(xmin, ymin, xmax, ymax)}
    boxes = {}
    if not im:
        print 'im should not be null'
        return [xTotal,yTotal],boxes
    if not ftName:
        ftName, font = random.choice(res['font'].items())
    else:
        font = res['font'][ftName]
    if not text:
        length = random.randint(1, TEXT_LENGTH_MAX)
        for i in range(length):
            text = text + random.choice(res['char'])
    d = ImageDraw.Draw(im)
    xMax = x0 + w0
    yMax = y0 + h0
    xOffset = 0
    yOffset = 0
    if randPos:
        xOffset = random.randint(0, int(w0/4))
    x1 = x0+xOffset
    y1 = y0+yOffset
    w = w0-xOffset
    h = h0-yOffset
    if w<=0 or h<=0:
        return [xTotal,yTotal],boxes
    if not color:
        color = getColor(im,x1,y1,w,h)
    for ch in text:
        size = d.textsize(ch, font=font)
        x2,y2 = x1+size[0], y1+size[1]
        if x2>=xMax or y2>=yMax:
            #print 'addtext break since text size:%s larger than im size:%s'\
            #       %((x1,y1,x2,y2), (x0,y0,x0+w,x0+h))
            break
        #print 'add text:%s size:%s at:%d,%d,%d,%d'%(ch,size,x1,y1,x2,y2)
        d.text((x1,y1), ch, font=font, fill=color)
        if not ch in boxes:
            boxes[ch] = [(x1,y1,x2,y2)]
        else:
            boxes[ch].append((x1,y1,x2,y2))
        if drawBox:
            d.rectangle([x1,y1,x2,y2], outline=(0,0,0))
        if xTotal == 0:
            xTotal = xOffset
        xTotal = xTotal+size[0]
        if yTotal<size[1]:
            yTotal = size[1]
        x1 = x2
    print "TAG: End addText:%s(%d,%d,%d,%d), boxes:%s"%(text,x0,y0,xTotal+x0,yTotal+x0, boxes)
    return [xTotal,yTotal],boxes


# "ImageSizes":["50*30","50*50","100*30","100*100","200*30","200*200"],
def loadSizeRange(res, cfg):
    res['size'] = {}
    for name in cfg["ImageSizes"]:
        (w,h) = name.split('*')
        # Validation width and height
        w = int(w)
        h = int(h)
        assert w<=WIDTH_MAX and h<=HEIGHT_MAX
        res['size'][name] = (w,h)
    

def createImage(res, size):
    bgname, bg = random.choice(res['bg'].items())
    xMin,yMin = 0,0
    w,h = bg.size
    # reserver board area to avoid background noise
#    if w>=150 and h>=150:
#        # if this is a big bg image, reserver 50*50
#        dw,dh = 50,50
#    else:
#        # if this is a small bg image, reserver 5*5
    dw,dh = 5,5
    w = w-dw
    h = h-dh
    xMin = xMin+dw
    yMin = yMin+dh
    # calculate a random start point
    # bg size should larger than image size
    if w<size[0] or h <size[1]:
        print "bg:%s size:%s(before board reserve) is not enought \
               for image size:%s"%(bgname, bg.size, size)
        return None
    x1 = random.choice(range(xMin, xMin+w-size[0]))
    y1 = random.choice(range(yMin, yMin+h-size[1]))
    box = (x1,y1,x1+size[0],y1+size[1])
    im = bg.crop(box)
    return im

def initRes():
    logger.info('LOADING configs')
    fin = open('config.json', 'r')
    cfg = json.load(fin)
    fin.close()
    res = {}
    # init res
    loadBGFile(res, cfg)
    loadNoise(res, cfg)
    loadFontFile(res, cfg)
    loadCharRange(res, cfg)
    loadSizeRange(res, cfg)
    print "==============================="
    print res
    return res

def testFont():
    res = initRes()
    w,h = 200,200
    im = res['bg'][str((0,0,0))].copy()
    d = ImageDraw.Draw(im)
    y1 = 10
    defName = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
    for fontName in res['font']:
        size,boxes = addText(0,y1,im.size[0],im.size[1]-y1,res,im,drawBox=True,ftName=defName,text=fontName,randPos=False)
        y1 = y1+size[1]
        size,boxes = addText(0,y1,im.size[0],im.size[1]-y1,res,im,drawBox=True,ftName=fontName,text=res['char']+"abcdABCD",randPos=False)
        y1 = y1+size[1]
    im.show()
        
    

def main(imNum, tensorPath, dataPath, modelPath, drawBox=False):
    res = initRes()
    voc = VocCreator(dataPath, os.path.join(modelPath,'pascal_label_map.pbtxt'))
    #for n in range(cfg['ImageNum']):
    for n in range(imNum):
        allBoxes = {}
        imName = 'im%04d'%(n)
        bgName, (w0,h0) = random.choice(res['size'].items())
        im = createImage(res, (w0,h0))
        if not im:
            continue
        x0,y0 = 0,0
        #print "add first Text:(%d,%d,%d,%d)"%(x0,y0,w0,h0)
        # Add at lease one text line
        size,boxes = addText(x0,y0,w0,h0,res,im,drawBox=drawBox)
        allBoxes.update(boxes)
        # try add more text line with noise
        while True:
            if not size or list(size)==[0,0]:
                break
            h0 = h0-size[1]
            yOffset = random.randint(0, int(h0/3))
            h0 = h0-yOffset
            y0 = y0+size[1]+yOffset
            size = [0,0]
            # Add Noise before text of this line
            noise = random.choice(res['noise'])
            if noise:
                #print "add noise before:%s(%d,%d,%d,%d)"%(noise,x0,y0,w0,h0)
                temp,boxes = addText(x0,y0,w0,h0,res,im,text=noise,randPos=False)
                if not temp or list(temp)==[0,0]:
                    break
                size[0] = size[0]+temp[0]
                if temp[1]>size[1]:
                    size[1] = temp[1]
                #print "temp=%s, x0=%d, w0=%d"%(temp,x0,w0)
            # Add formal text of this line
            #print "add middle Text:(%d,%d,%d,%d)"%(x0,y0,w0,h0)
            temp,boxes = addText(x0+size[0],y0,w0-size[0],h0,res,im,drawBox=drawBox)
            allBoxes.update(boxes)
            if not temp or list(temp)==[0,0]:
                break
            size[0] = size[0]+temp[0]
            if temp[1]>size[1]:
                size[1] = temp[1]
            # Add Noise after text of this line
            noise = random.choice(res['noise'])
            if noise:
                #print "add noise after:%s(%d,%d,%d,%d)"%(noise,x0,y0,w0,h0)
                temp,boxes = addText(x0+size[0],y0,w0-size[0],h0,res,im,text=noise,randPos=False)
                if not temp or list(temp)==[0,0]:
                    break
                size[0] = size[0]+temp[0]
                if temp[1]>size[1]:
                    size[1] = temp[1]
        if drawBox:
            im.show()
        voc.addImage(imName, im, allBoxes)
    voc.finish()
    #create_pascal_tf_record.py --data_dir=./ocr03/ --year=VOC2012
    #                           --output_path=ocr03_val.record --set=val
    #                           --label_map_path=./ocr03/pascal_label_map.pbtxt
    cmdPath = os.path.join(tensorPath, 'create_pascal_tf_record.py')
    labelPath = os.path.join(dataPath, 'pascal_label_map.pbtxt')
    valOutput = os.path.join(modelPath, '%s_val.record'%(dataPath.split('/')[-1]))
    trainOutput = os.path.join(modelPath, '%s_train.record'%(dataPath.split('/')[-1]))
    valCmd = 'python %s --data_dir=%s --year=VOC2012 --set=val\
                --output_path=%s --label_map_path=%s'\
                %(cmdPath, dataPath, valOutput, labelPath)
    os.system(valCmd)
    trainCmd = 'python %s --data_dir=%s --year=VOC2012 --set=train\
                --output_path=%s --label_map_path=%s'\
                %(cmdPath, dataPath, trainOutput, labelPath)
    os.system(trainCmd)
    # copy new create labelmap to model path
    shutil.copy(labelPath, modelPath)


ROOT_PATH='/home/leo/qj/object_detection'
#ROOT_PATH='/tmp/leo'

TENSOR_PATH=ROOT_PATH
DATA_PATH='%s/data/origin/socr_%s'\
            %(ROOT_PATH,datetime.datetime.now().strftime("%Y%m%d"))
MODEL_PATH='%s/data/socr'%(ROOT_PATH)

main(1000, TENSOR_PATH,DATA_PATH,MODEL_PATH,drawBox=False)
#testFont()

