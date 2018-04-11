import os
import re
import errno
from lxml import etree, objectify
from PIL import Image
import shutil
import random


class VocCreator:
    # pascal_label_map.pbtxt format is as below:
    # "item {\r\n id: 1\r\n name: 'Actor'\r\n}\r\nitem {\r\n id: 2\r\n name:
    # 'Guider'\r\n}\r\nitem {\r\n id: 3\r\n name: 'Boss'\r\n}\r\n"
    def loadMapFile(self, labelMapFile):
        label ={}
        f = open(labelMapFile)
        string1 = f.read()
        #replace [\r\n\f\t\r\v ] with single space ' ' 
        #s2="item { id: 1 name: 'Actor' } item { id: 2 name: 'Guider' } item { id: 3 name: 'Boss' }"
        s2 = re.sub(r'\s+',' ',string1)
        #remove "item {"
        #s3="id: 1 name: 'Actor' } id: 2 name: 'Guider' } id: 3 name: 'Boss' }"
        s3 = re.sub('item\s*{\s*','',s2)
        #split {id: xx name: xx} into a group list
        #l=["id: 1 name: 'Actor'", "id: 2 name: 'Guider'", "id: 3 name: 'Boss'", '']
        l = re.split(r'\s*}\s*', s3)
        for member in l:
            # match id=r.group(1), name=r.group(2)
            r = re.match(r'\s*id:\s*([0-9]*)\s+name:\s*[\'\"]*([a-zA-Z0-9]*)', member)
            if not r: continue
            # put labelMap[name] = int(id)
            label[r.group(2)] = int(r.group(1))
        f.close()
        return label

    # "item {\r\n id: 1\r\n name: 'Actor'\r\n}\r\nitem {\r\n id: 2\r\n name:
    # 'Guider'\r\n}\r\nitem {\r\n id: 3\r\n name: 'Boss'\r\n}\r\n"
    def saveMapFile(self, labelMap, labelMapFile):
        f = open(labelMapFile, 'w')
        s = ''
        for name in sorted(labelMap, key=labelMap.get):
            i = labelMap[name]
            s = s+"item {\r\n id: %d\r\n name: '%s'\r\n}\r\n"%(i,name)
        f.write(s)
        
    def __init__(self, path, labelMapFile=''):
        self.JPEGImages = os.path.join(path, 'JPEGImages/')
        self.Annotations = os.path.join(path, 'Annotations/')
        self.ImageSetsMain = os.path.join(path, 'ImageSets/Main/')
        self.LabelMapFile = os.path.join(path, 'pascal_label_map.pbtxt')
        self.imFilePaths = []
        self.labelMap = {}
        if labelMapFile:
            if os.path.isfile(labelMapFile):
                self.labelMap = self.loadMapFile(labelMapFile)
            else:
                print "labelMapFile:%s does not exist, skip it and create new"%(labelMapFile)
        for folder in ('Annotations', 'ImageSets', 'JPEGImages', 'ImageSets/Main'):
            name = os.path.join(path, folder)
            try:
                os.makedirs(name)
            except OSError as e:
                if e.errno != errno.EEXIST:
                    raise
                else:
                    delete_prompt = raw_input('Directorie:%s already exist. Do you want to delete it? [y/n]: '%(name))
                    if delete_prompt == 'y':
                        shutil.rmtree(name)
                        os.makedirs(name)
                    elif delete_prompt == 'n':
                        break
                    else:
                        raise ValueError('Possible choices are yes-\'y\' or no-\'n\'')


    def addImage(self, filename, im, boxes):
        """filename is without ext: 001
           im is a PIL Image object
           boxes is: {tag:[(xmin, ymin, xmax, ymax)]}
           path is where to store VOC Pascal files
        """
        print "addImage",filename,boxes
        imFilePath = os.path.join(self.JPEGImages, filename+'.jpg')
        annoFilePath = os.path.join(self.Annotations, filename+'.xml')
        assert not os.path.isfile(imFilePath),\
            "file is dup:%s"%(imFilePath)
        assert not os.path.isfile(annoFilePath),\
            "file is dup:%s"%(annoFilePath)
        #create JPEGImages file
        im.save(imFilePath, 'JPEG')
        #create Annotations file
        self.createAnno(imFilePath, annoFilePath, im.size, boxes)
        self.imFilePaths.append(imFilePath)
        
    def finish(self):
        # sperate imFiles into two group
        trainFilePath = os.path.join(self.ImageSetsMain, 'train.txt')
        valFilePath = os.path.join(self.ImageSetsMain, 'val.txt')
        # shuffle the input files
        random.shuffle(self.imFilePaths)
        # 85% put into train group
        n = int(len(self.imFilePaths)*0.85)
        trainSets = self.imFilePaths[:n]
        f = open(trainFilePath, 'w')
        for name in trainSets:
            # Set all image file as positive sample
            # filename 1  --- positive sample
            # filename -1 --- negitive sample
            basename = os.path.basename(name)
            purename = os.path.splitext(basename)[0]
            f.write("%s 1\n"%(purename))
        f.close()
        # 15% put into val group
        valSets = self.imFilePaths[n:]
        f = open(valFilePath, 'w')
        for name in valSets:
            # Set all image file as positive sample
            basename = os.path.basename(name)
            purename = os.path.splitext(basename)[0]
            f.write("%s 1\n"%(purename))
        f.close()
        # write tag and id map file 
        self.saveMapFile(self.labelMap, self.LabelMapFile)
        
    def createAnno(self, imFilePath, annoFilePath, size, boxes):
        """boxes is: {tag:(xmin, ymin, xmax, ymax)}
           size is: (width, height)"""
        relpath = os.path.relpath(imFilePath, os.path.dirname(annoFilePath))
        basename = os.path.basename(imFilePath)
        # Tensorflow tool do not need image ext name 
        purename = os.path.splitext(basename)[0]
        E = objectify.ElementMaker(annotate=False)
        anno = E.annotation(
            E.folder('Annotation'),
            E.filename(purename),
            E.path(relpath),
            E.source(
                E.database('Unkown'),
            ),
            E.size(
                E.width(size[0]),
                E.height(size[1]),
                E.depth(3)
            ),
            E.segmented(0)
        )
        for tag in boxes:
            # each tag may contain multiple box area
            # boxes = [(0,0,100,100),(30,30,50,50)]
            # unify it to list format
            if not isinstance(boxes[tag], list):
                boxes[tag] = [boxes[tag]]
            for box in boxes[tag]:
                #print box
                E = objectify.ElementMaker(annotate=False)
                anno.append(
                    E.object(
                    E.name(tag),
                    E.pose('Unspecified'),
                    E.bndbox(
                        E.xmin(box[0]),
                        E.ymin(box[1]),
                        E.xmax(box[2]),
                        E.ymax(box[3])
                    ),
                    E.difficult(0)
                    )
                )
            # add new tag into self.labelMap
            #print("TAG:add tag:",tag)
            if not tag in self.labelMap:
                newID = 1
                if self.labelMap:
                    newID = max(self.labelMap.values())+1
                self.labelMap[tag] = newID
                #print("TAG:new tag:%s, id:%d. founded"%(tag,newID))
        etree.ElementTree(anno).write(annoFilePath, pretty_print=True)
        #print("anno is:%s"%(etree.tostring(anno, pretty_print=True)))
        return anno


#boxes = {'face':(0,0,100,100), 'leg':[(10,10,30,30),(90,90,100,100)]}
#im = Image.open('bg/bg1.jpeg')
#path = '/tmp/leo/ocrtest/'
#voc = VocCreator(path, 'test/pascal_label_map.pbtxt')
#for name in ['001','002','003']:
#    voc.addImage(name, im, boxes)
#voc.finish()

