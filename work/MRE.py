"""
Created on Wed Aug 19 10:18:45 2020

@author: Waldo

@version: 0.3

"""

from os import scandir, unlink, mkdir
from os.path import isdir, isfile
from random import shuffle

__InternalKeyValueSeparator = "\x03"
InputKeyValueSeparator = "\t"
OutputKeyValueSeparator = "\t"
MaxForCombiner = 10

class _TreeNode:
    def __init__(this, key, value):
        this.__key = key
        this.__values = [(key, value)]
        this.__left = None
        this.__right = None
        
    def _getValues(this):
        return this.__values
        
    def print(this):
        if not(this.__left is None):
            this.__left.print()
            
        print(str(this.__key) + " ==> " + str(this.__values))
            
        if not(this.__right is None):
            this.__right.print()
        
    def getKey(this):
        return this.__key
    
    def getLeft(this):
        return this.__left
    
    def getRight(this):
        return this.__right
    
    def setLeft(this, left):
        this.__left = left
        
    def setRight(this, right):
        this.__right = right
        
    def add(this, value):
        this.__values.append(value)
        
    def count(this):
        return len(this.__values)
    
    def getAndEmptyValues(this):
        v=[]
        for t in this.__values:
            v.append(t[1])
        this.__values = []
        return v
    
    def getAllValues(this, values):
        if not(this.__left is None):
            this.__left.getAllValues(values)
            
        for t in this.__values:
            values.append(t[1])

        if not(this.__right is None):
            this.__right.getAllValues(values)
        
    def __addOrUpdate(this, aTree, key, value, cmp):
        if aTree is None:
            aTree = _TreeNode(key, value)
        else:
            _tree = aTree
            buscar = True
            while buscar:
                c = cmp(key, _tree.getKey())
                if c == 0:
                    _tree.add((key, value))
                    buscar = False
                elif c < 0:
                    if(_tree.getLeft() is None):
                        _tree.setLeft(_TreeNode(key, value))
                    else:
                        _tree = _tree.getLeft()
                else:
                    if(_tree.getRight() is None):
                        _tree.setRight(_TreeNode(key, value))
                    else:
                        _tree = _tree.getRight()
        return aTree
    
    def collect(this, dic, fsort):
        nodos = [this]
        while len(nodos) > 0:
            _tree = nodos[0]
            del(nodos[0])
            tmpTree = None
            for t in _tree._getValues():
                tmpTree = this.__addOrUpdate(tmpTree, t[0], t[1], fsort)
            values = []
            tmpTree.getAllValues(values)
               
            dic[_tree.__key] = values
        
            if not(_tree.getLeft() is None):
                nodos.append(_tree.getLeft())
            
            if not(_tree.getRight() is None):
                nodos.append(_tree.getRight())

def fDefaultCmp(a, b):
    if a == b:
        return 0
    elif a < b:
        return -1
    else:
        return 1
    
class _Context:
    def __init__(this, _inputs, output, fComb, params, fShuffleCmp, fSortCmp):
        this.__inputs = _inputs
        this.__stage = 0 #map
        this.__output = output
        
        this.__interm = None
        this.__result = []
        
        this.__params = params
        this.__fComb = fComb
        this.__fShuffleCmp = fShuffleCmp
        this.__fSortCmp = fSortCmp
        
    def __iter__(this):
        if(this.__stage == 0):
            return _MapIterator(this.__inputs)
        elif(this.__stage == 3):
            _dict = {}
            this.__interm.collect(_dict, this.__fSortCmp)
            return _Reduceterator(_dict)
        else:
            return None
        
    def finish(this):
        if (isdir(this.__output)):
            files = [obj.name for obj in scandir(this.__output) if obj.is_file()]
            for f in files: 
                fp = this.__output + "/" + f
                if isfile(fp): 
                    unlink(fp) 
        else:
            mkdir(this.__output)
        f = open(this.__output + "/output.txt", "w+")
        for t in this.__result:
            f.write(this.__flat(t[0]) + OutputKeyValueSeparator + this.__flat(t[1]) + "\n")
        f.close()
    
    def __flat(this, obj):
        if(type(obj) is tuple) or (type(obj) is list):
            res = ""
            for v in obj:
                res = res + this.__flat(v) + OutputKeyValueSeparator
            res = res[:-1]
        else:
            res = str(obj)
        
        return res        
        
    def startReduce(this):
        this.__stage = 3 # reduce
        
    def __addOrUpdateKey(this, aTree, key, value, cmp):
        if aTree is None:
            aTree = _TreeNode(key, value)
        else:
            buscar = True
            _tree = aTree
            while buscar:
                c = cmp(key, _tree.getKey())
                if c == 0:
                    _tree.add((key, value))
                    if(_tree.count() > MaxForCombiner):
                        this.__executeCombiner(_tree)
                    buscar = False
                    
                elif c < 0:
                    if(_tree.getLeft() is None):
                        _tree.setLeft( _TreeNode(key, value) )
                        buscar = False
                    else:
                        _tree = _tree.getLeft()
                else:
                    if(_tree.getRight() is None):
                        _tree.setRight( _TreeNode(key, value) )
                        buscar = False
                    else:
                        _tree = _tree.getRight()
        return aTree
    
    def write(this, k, v):
        if (this.__stage == 0):
            # map            
            this.__interm = this.__addOrUpdateKey(this.__interm, k, v, this.__fShuffleCmp)
            
        elif (this.__stage == 3):
            # reduce
            this.__result.append((k, v))
            
    def __getitem__(this, index):
        return this.__params[index]
    
    def __executeCombiner(this, tree):
        if(this.__fComb is None):
            return
        
        values = tree.getAndEmptyValues()

        this.__fComb(tree.getKey(), values, this)
        
    
class _MapIterator:
    def __init__(this, _inputs):
        this.__inputs = _inputs
        this.__currentInput = 0
        this.__initInput(this.__currentInput)
        
    def __initInput(this, ci):
        if ci < len(this.__inputs):
            this.__currentDir = this.__inputs[ci][0]
            this.__currentFuncMap = this.__inputs[ci][1]
            if(this.__currentFuncMap is None):
                this.__currentInput = this.__currentInput + 1
                return this.__initInput(this.__currentInput)
            else:
                this.__files = [obj.name for obj in scandir(this.__currentDir) if obj.is_file()]
        else:
            this.__files = []
        this.__currentFile = 0        
        this.__initFile(this.__currentFile)
        
    def __initFile(this, cf):
        if cf < len(this.__files):
            f = open(this.__currentDir + "/" + this.__files[cf], "r", encoding='latin-1')
            this.__lines = f.readlines()
            shuffle(this.__lines)
            f.close()
        else:
            this.__lines = []
        this.__currentLine = 0 
        this.__offset = 0
        
    def __next__(this):
        if(this.__currentInput >= len(this.__inputs)):
            raise StopIteration
			
        elif(this.__currentFile >= len(this.__files)):
            this.__currentInput = this.__currentInput + 1
            this.__initInput(this.__currentInput)
            return this.__next__()
            
        elif (this.__currentLine >= len(this.__lines)):
            this.__currentFile = this.__currentFile + 1
            this.__initFile(this.__currentFile)
            return this.__next__()
            
        else:
            line = this.__lines[this.__currentLine]
            line = line[:-1]
            if(line.find(InputKeyValueSeparator) >= 0):
                (k,v) = line.split(InputKeyValueSeparator, 1)
            else:
                (k,v) = (this.__offset, line)
            this.__offset = this.__offset + len(this.__lines[this.__currentLine])
            this.__currentLine = this.__currentLine + 1
            return (this.__currentFuncMap, k,v)

class _Reduceterator:
    def __init__(this, _dict):
        this.__dict = _dict
        this.__keys = list(this.__dict.keys())
        this.__keys.sort()
        this.__currentKey = 0
        
    def __next__(this):
        if(this.__currentKey >= len(this.__keys)):
            raise StopIteration
        else:
            k = this.__keys[this.__currentKey]
            v = this.__dict[k]
            this.__currentKey = this.__currentKey + 1
            return (k,v)
    
class Job:
    def __init__(this, _input, output, fMap, fReduce):
        this.__inputs = [(_input, fMap)]
        this.__fReduce = fReduce
        this.__fComb = None
        this.__output = output
        this.__params = None
        this.__fShuffleCmp = fDefaultCmp
        this.__fSortCmp = fDefaultCmp
        
    def setShuffleCmp(this, fShuffleCmp):
        this.__fShuffleCmp = fShuffleCmp
        
    def setSortCmp(this, fSortCmp):
        this.__fSortCmp = fSortCmp
        
    def setParams(this, params):
        this.__params = params
        
    def setCombiner(this, fComb):
        this.__fComb = fComb
        
    def __map(this, context):
        for (f, k,v) in context:
            f(k, v, context)
            
    def __sort(this, context):
        pass
    
    def __shuffle(this, context):
        pass
            
    def __reduce(this, context):
        context.startReduce()
        for (k,vs) in context:
            this.__fReduce(k, vs, context)
        
    def waitForCompletion(this):
        context = _Context(this.__inputs, this.__output, this.__fComb, this.__params, this.__fShuffleCmp, this.__fSortCmp)
        this.__map(context)
        this.__shuffle(context)
        this.__sort(context)
        this.__reduce(context)
        context.finish()
        
        return True
        
    def addInputPath(this, _input, fmap):
        this.__inputs.append((_input, fmap))
