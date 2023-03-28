import json
from pathlib import Path
import pandas as pd, numpy as np
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from copy import deepcopy
from pydantic.utils import deep_update

def nan2None(obj):
    if isinstance(obj, dict):
        return {k:nan2None(v) for k,v in obj.items()}
    elif isinstance(obj, list):
        return [nan2None(v) for v in obj]
    elif isinstance(obj, float) and np.isnan(obj):
        return None
    return obj
class NanConverter(json.JSONEncoder):
    def default(self, obj):
        # possible other customizations here 
        pass
    def encode(self, obj, *args, **kwargs):
        obj = nan2None(obj)
        return super().encode(obj, *args, **kwargs)
    def iterencode(self, obj, *args, **kwargs):
        obj = nan2None(obj)
        return super().iterencode(obj, *args, **kwargs)
    
def loadTimeCapsule(outJSON,tcdf,attrz=None,layout={},data={},
                    ytitle=None,JSONindent=None):
    '''load outJSON with specified data according to the timecapsule specification\n
    tcdf.index is the unified X axis, with xtitle as tcdf.index.name\n
    ytitle is the title of the y axis\n
    each col of tcdf is a separate feature to be plotted, with the col name as the feature name\n
    attrz: dict of attrz OR func which takes tcdf and computes its attrz\n
    layout: dict to be fed to plotly JS layout property, as specified here \n
    https://plotly.com/javascript/reference/layout/
    '''
    #TODO if series col = 0
    df = pd.DataFrame(tcdf)
    if is_datetime(df.index):
        X = df.index.strftime('%Y-%m-%d %X').to_list()
    else:
        X = df.index.to_list()
        
    lyt = deepcopy(layout)

    xtitle = df.index.name
    if xtitle:
        lyt = deep_update(lyt,{
            'xaxis': {
                'title':{'text':xtitle}}
        })
    if ytitle:
        lyt = deep_update(lyt,{
            'yaxis': {
                'title':{'text':ytitle}}
        })
    
    jsn = {
        'x':X,
        'data':[
            {'name':col,
            'y':df[col].to_list(),
             **data
            } for col in df.columns
        ],
        'layout':lyt
    }
    
    if attrz:
        attrs = attrz(df) if callable(attrz) else attrz
        jsn.update({'attrz':attrs})

    with open(outJSON, 'w') as outfile:
        json.dump(jsn , outfile,
                cls=NanConverter,
                indent=JSONindent
                )

# attrz helper funcs:
def attrzFromDict(attrzdict):
    '''returns attrz format dict with key,value explicit\n
    {'Name': '0638', 'corr': 0.81, 'MAE': 0.46, 'RMSE': 0.56, 'NSE': 0.54}\n
    =>\n
    [{'key': 'Name', 'value': '0638'},\n
    {'key': 'corr', 'value': 0.81},\n
    {'key': 'MAE', 'value': 0.46},\n
    {'key': 'RMSE', 'value': 0.56},\n
    {'key': 'NSE', 'value': 0.54}]\n
    '''
    attrz = [
    {
        'key':key,
        'value':val,
    } for key,val in attrzdict.items() ]
    return attrz

def addBound(attrz,key,lbound=None,rbound=None):
    '''update attrz object in place with lbound,rbound at key'''
    df = pd.DataFrame(attrz)
    idx = df[df.key==key].index[0]

    if lbound:
        attrz[idx].update({'lbound':lbound})
    if rbound:
        attrz[idx].update({'rbound':rbound})

def addBounds(attrz,bounds):
    '''add bounds to attrz in place\n
    bounds in form\n
    bounds = {\n
        'corr':{'lbound':0.9},\n
        'MAE':{'rbound':0.75},\n
        'RMSE':{'rbound':0.75},\n
        'NSE':{'lbound':0.5},\n
    }'''
    [addBound(attrz,key,**kwargz) for key,kwargz in bounds.items()]