import json
from pathlib import Path
import pandas as pd, numpy as np
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from copy import deepcopy
from pydantic.utils import deep_update
import xarray as xr
# from funkshuns import *

try:
    from collections import Iterable
except:
    from collections.abc import Iterable 
def isiter(obj):
    '''True if iterable, False if string type, b'string', (geo)pandas obj, or not iterable'''
    return (
        isinstance(obj, Iterable) 
        and not isinstance(obj, str)
        and not isinstance(obj,bytes)
        and not isinstance(obj,pd.Series)
        and not isinstance(obj,pd.DataFrame)
    )
def bold(st):
    '''wrap st with <b> tags, apply to each st in iterable if st is iterable'''
    if isiter(st):
        return [bold(i) for i in st]
    return st if str(st).startswith('<b>') else f'<b>{st}</b>'
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
    
def deposit(outJSON,tcdf,attrz=None,layout={},data={},
                    xtitle=None,ytitle=None,JSONindent=None):
    '''bounce outJSON timecapsule with specified data according to the timecapsule specification\n
    tcdf.index is the unified X axis, with xtitle as tcdf.index.name\n
    ytitle is the title of the y axis\n
    each col of tcdf is a separate feature to be plotted, with the col name as the feature name\n
    attrz: dict of attrz OR func which takes tcdf and computes its attrz\n
    layout: dict to be fed to plotly JS layout property, as specified here \n
    https://plotly.com/javascript/reference/layout/\n\n

    data adds values to data for each trace, OR you may also pass in funcs for dict values as desired and it will compute the function on df[col] for each\n

        jsn = {
        'x':X,
        'data':[
            {'name':col,
            'y':df[col].to_list(),
            **{key:val if not hasattr(val,'__call__') else val(df[col])
                 for key,val in data.items() }
            } for col in df.columns
        ],
        'layout':lyt
    }
    \n\n
    returns jsn
    '''
    #TODO if series col = 0
    df = pd.DataFrame(tcdf)
    if is_datetime(df.index):
        X = df.index.strftime('%Y-%m-%d %X').to_list()
    else:
        X = df.index.to_list()
    # because NaNs screw up json, this is dealt with in the cls,
    #  but passing the dict obj to an api will need this handled first
    X = nan2None(X) 
        
    lyt = deepcopy(layout)

    xtitle = df.index.name
    if xtitle:
        lyt = deep_update(lyt,{
            'xaxis': {
                'title':{'text':xtitle}}
        })
    ytitle = ytitle or df.columns.name
    if ytitle:
        lyt = deep_update(lyt,{
            'yaxis': {
                'title':{'text':ytitle}}
        })
    
    jsn = {
        'x':X,
        'data':[
            {'name':col,
            'y':nan2None( df[col].to_list() ),
            **{key:val if not hasattr(val,'__call__') else val(df[col])
                 for key,val in data.items() }
             
            } for col in df.columns
        ],
        'layout':lyt
    }
    
    if attrz:
        attrs = attrz(df) if callable(attrz) else attrz
        # demo
        # if 'oops' in attrs.keys():
        #     attrs.pop('oops')
        jsn.update({'attrz':attrs})

    if outJSON:
        with open(outJSON, 'w') as outfile:
            json.dump(jsn , outfile,
                    cls=NanConverter,
                    indent=JSONindent
                    )
    
    return jsn

def depositDSsuite(ds,outsuitepth,
            ytitle='WSEL (ft)',
            trialdim='plan',
            tdim = 'Time (UTC)',
            STAdim = 'Gauge',
            outHTMLdir=None,
            htmlsuffstr='',
        ):
    '''if outHTMLdir, bounce each trial (along trialdim) in DS suite there\n
    htmlsuffstr: additional text in outHTMLdir/f'{plan}{htmlsuffstr}.html' outputs'''
    assert set(ds.dims) == {tdim,STAdim,trialdim}, (set(ds.dims) ,{tdim,STAdim,trialdim})

    planz = ds[trialdim].values
    for plan in planz:
        outtrialpth = outsuitepth/str(plan)
        pln = ds.sel({trialdim:plan})
        pln=pln.drop(trialdim)
        depositDStrial(pln,outtrialpth,ytitle=ytitle,tdim=tdim,STAdim=STAdim,
            outHTML=outHTMLdir/f'{plan}{htmlsuffstr}.html' if outHTMLdir else None)

def depositDStrial(ds,outtrialpth,
            outHTML=None,
            ytitle='WSEL (ft)',
            tdim = 'Time (UTC)',
            STAdim = 'Gauge'
        ):
    '''if outHTML Path, plot full trial there'''
    assert set(ds.dims) == {tdim,STAdim}, (set(ds.dims) ,{tdim,STAdim})
    
    outtrialpth.mkdir(parents=True,exist_ok=True)
    gauges = ds[STAdim].values
    for gaugename in gauges:
        tcjson = outtrialpth/f'ts_{gaugename}.json'
        gage = ds.sel({STAdim:gaugename})
        gage=gage.drop(STAdim)
        depositDS(gage,tcjson,ytitle=ytitle,tdim=tdim)

    print(f'Serialized to {outtrialpth}')

    if outHTML:
        outHTML.parent.mkdir(parents=True,exist_ok=True)
        toHTML(outtrialpth,outHTML)
        print(f'{outtrialpth} plotted to {outHTML}')

def depositDS(ds,tcjson,
            ytitle='WSEL (ft)',
            tdim = 'Time (UTC)',
        ):
    '''at gaugename to timecapsule'''
    assert set(ds.dims) == {tdim}, (set(ds.dims) ,tdim)
    all_coords = set(ds.coords)
    dim_coords = set(ds.dims)
    non_dim_coords = all_coords - dim_coords

    gage = ds.drop_vars(non_dim_coords)
    df = gage.to_pandas()

    deposit(tcjson,df,ytitle=ytitle,data={'line':{'width':1}})
    print(f'Bounced to {tcjson}')


from pathlib import Path
import pandas as pd, numpy as np
import json
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from copy import deepcopy
import subprocess

class _emptyLister(dict):
    def __missing__(self, key):
        return []
class _emptyDict(dict):
    def __missing__(self, key):
        return {}
def _bothBounds(bnds):
    bnd = {'lbound':-9999999999,'rbound':999999999999}
    bnd.update(bnds)
    return bnd

# plotting TODO separate .py

alpha=0.4
def plot(timecapsule,title='',
    width=1600,height=600,
    cmap=["#b3294e","#4829B2",'#0ff54c','#f2b200'],
    bgcolor = 'hsl(210, 10%, 60%)',
    bounds=None,
    green=f'rgba(0, 255, 64,{alpha})',
    red=f'rgba(255, 0, 34,{alpha})',
    ):
    '''timecapsule: Path to json or dict object'''

    # read in tc
    tc = deepcopy(timecapsule) if isinstance(timecapsule,dict) \
        else json.load(open(timecapsule)) 


    # creates list of subplot formats to plot tables properly
    specsInput=[[{'type':'xy'},{'type':'domain'}]]#*len(tcs)

    absTblWidth = 350
    column_widths = [(width-absTblWidth)/width , absTblWidth/width]
    # creates figure and sets number of rows and columns, relative column widths, spacings between plots, titles, and formats
    # print('DATA?','data' in tc)
    # print(bold(title) if 'data' in tc else 'no data')

    fig=make_subplots(
        rows=1,
        cols=2,
        column_widths=column_widths,
        vertical_spacing=0.02,
        horizontal_spacing=0.02,
        subplot_titles=[bold(title) if 'data' in tc else '',''],#*len(tcs)*2,
        specs=specsInput)
    
    # add scatter plot if tc['data']
    [
    fig.add_trace(
        go.Scatter(x=tc['x'],
            **({'marker':{'color':cmap[i]}} if len(cmap)>i else {}),
            **{'mode':'lines',# defaults
                **data}, # defaults get overriden if they appear in data
            ),
    row=1,
    col=1)
        for i,data in enumerate(_emptyLister(tc)['data'])
    ]

    #add table
    if 'attrz' in tc:
        # demo
        if 'oops' in tc['attrz'].keys():
            tc['attrz'].pop('oops')

        key = list(tc['attrz'].keys())[0]
        headr = [key, tc['attrz'].pop(key) ]
        headr = bold(headr)

        # attrz bounds logic setup:
        if bounds:
            # add bounds for items prepended by 'Mean ' as well
            boundz = { **bounds,
                **{f'Mean {key}':val for key,val in bounds.items()} }
            boundz = {col:_bothBounds(bnds) for col,bnds in boundz.items()}
            def testbounds(key,val):
                if key not in boundz:
                    return 'rgba(0,0,0,0)' 
                if val is None:
                    return red
                if      val >= boundz[key]['lbound'] \
                    and val <= boundz[key]['rbound']:
                    return green 
                else:
                    return red

        fig.add_trace(go.Table(
            # columnwidth=300000000000000,
            header=dict(values=headr,
                        fill_color='rgba(0,0,0,0)',
                        font=dict(size=14),
                                    # align='center'
                                    ),
                cells=dict(values=[
                    bold(
                        list(tc['attrz'].keys())
                    ),
                        list(tc['attrz'].values())
                    ],
                            fill_color=[[
                                testbounds(key,val) 
                                    if bounds else 'rgba(0,0,0,0)'
                                        for key,val in tc['attrz'].items() 
                            ]]*2,

                                    # font=dict(
                                    #     family='roboto',
                                    #     size=16),
                        # align='',
                            ),
                        # format=['','.2f','.2f'],
                        # height=30
                        ),
            row=1,
            col=2
            )

    # workaround for crappy plotly bug https://community.plotly.com/t/subplot-titles-disappearing-when-adding-annotations/5256/8
    annotations = [a.to_plotly_json() for a in fig["layout"]["annotations"]]
    lyt = {
        'paper_bgcolor':bgcolor,
        'plot_bgcolor':bgcolor,#'hsla(210, 26%, 14%, 0)',
        'margin': {
            'l': 40,
            'r': 50,
            "b": 40,
            't': 20,
            # // t: 40, //for plot title
            # 'pad': 20
        },
        'width':width,
        'height':height,#*len(tcs),
        'font': {
            # 'family': 'Roboto',
            # 'size': 18,
            'color': 'black'
        },
            'legend': {
                'bgcolor':bgcolor,
                'orientation': "v",
                'xanchor': "left",
                'yanchor': "bottom",
                'y': 1.0,
                'x': 0
            },
        **_emptyDict(tc)['layout']}

    if 'annotations' in lyt:
        # specifically subplot titles need to go first for some reason
        lyt['annotations'] = annotations + lyt['annotations']
    else:
        lyt['annotations'] = annotations
        
    fig=fig.update_layout(lyt)
    return fig

def boundsToEnglish(bounds,newline='<br>'):
    '''converts bounds dict to readable string'''
    reqs= []
    for col,bnds in bounds.items():
        if 'rbound' in bnds and 'lbound' in bnds:
            req = f"{bnds['lbound']} < {col} < {bnds['rbound']}"
        elif 'rbound' in bnds:
            req =f"{col} < {bnds['rbound']}"
        elif 'lbound' in bnds:
            req =f"{col} > {bnds['lbound']}"
        reqs += [req]
    reqs = newline.join(reqs)
    return reqs

htmlcfg = {'displaylogo': False,
    'modeBarButtonsToAdd':[
        # 'drawline',
        'drawopenpath',
        # 'drawclosedpath',
        # 'drawcircle',
        # 'drawrect',
        'eraseshape'
    ],
}

def toHTML(TCdir,outHTML,bounds=None,
    description=lambda reqs: f'Metric targets:<br>{reqs}',
    doctitle='How to use this document',
    plotTitleFunc=lambda nm: f'{nm} - Simulated vs Observed Stage',
    descriptionPadding=100,
    width=1600,
    height=600,
    bgcolor = 'hsl(210, 10%, 60%)',
    green=f'rgba(0, 255, 64,{alpha})',
    red=f'rgba(255, 0, 34,{alpha})',
    cmap=["#4829B2","#b3294e",'#0ff54c','#f2b200'],
    openHTML=True
    ):
    '''

    '''
    capsules = list(TCdir.glob('*.json'))
    # send insights to the front if it exists
    jsons = pd.Series(capsules)
    stems = jsons.map(lambda f:f.stem)
    insight = stems=='insights'
    jsons = jsons[insight].to_list() + jsons[~insight].to_list() 
    # [ print('TITLE',plotTitleFunc(jsn.stem.replace('ts_',''))) for jsn in jsons ]
    figz = [plot(jsn,
                title=plotTitleFunc(jsn.stem.replace('ts_','')),
                bounds=bounds,
                width=width,height=height,
                cmap=cmap,
                bgcolor = bgcolor,
                green=green,
                red=red)
            for jsn in jsons]
    
    # concat all to 1 html ala 
    # https://stackoverflow.com/questions/59868987/plotly-saving-multiple-plots-into-a-single-html/59869358#59869358
    divs =  ''.join([ fig.to_html(full_html=False, 
            config=htmlcfg,
            include_plotlyjs='cdn' if row==0 else False
            )
        for row,fig in enumerate(figz) ])

    descript = description(boundsToEnglish(bounds)) if bounds else description('N/A')

    padding=descriptionPadding
    absTblWidth = 350
    width1 = width-absTblWidth-padding*2
    height1=height-padding*2
    width1

    doc = '''
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{doctitle}</title>
    <link href='https://fonts.googleapis.com/css?family=Roboto' rel='stylesheet'>
    <style>
        .subplot1 {{
            width: {width1}px;
            height: {height1}px;
            position: absolute;
            padding: {padding}px;
            z-index: 105;
        }}
        body {{
            background-color: {bgcolor};
            font-family: Roboto, "Open Sans", Arial, Helvetica;
        }}
        .plotly-graph-div {{
            margin: auto;
            border-bottom:1px solid white;
        }}

    </style>
</head>
<body>
    <div class="subplot1">
        <h3>{doctitle}</h3>
        <p>{description}</p>
    </div>
    {divs}
    
</body>
</html>
'''
    doc = doc.format(**{'divs':divs,'bgcolor':bgcolor,'doctitle':doctitle,'description':descript,
        'width1':width1,'height1':height,'padding':padding})

    outHTML.unlink(missing_ok=True)
    outHTML.write_text(doc)
    print(f'plots from\n {TCdir} written to \n{outHTML}')
    if openHTML:
        # open in default web browser:
        subprocess.Popen([ "explorer", str(outHTML) ])

# attrz helper funcs:
# def attrzFromDict(attrzdict):
#     '''returns attrz format dict with key,value explicit\n
#     {'Name': '0638', 'corr': 0.81, 'MAE': 0.46, 'RMSE': 0.56, 'NSE': 0.54}\n
#     =>\n
#     [{'key': 'Name', 'value': '0638'},\n
#     {'key': 'corr', 'value': 0.81},\n
#     {'key': 'MAE', 'value': 0.46},\n
#     {'key': 'RMSE', 'value': 0.56},\n
#     {'key': 'NSE', 'value': 0.54}]\n
#     '''
#     attrz = [
#     {
#         'key':key,
#         'value':val,
#     } for key,val in attrzdict.items() ]
#     return attrz

# def addBound(attrz,key,lbound=None,rbound=None):
#     '''update attrz object in place with lbound,rbound at key'''
#     df = pd.DataFrame(attrz)
#     idx = df[df.key==key].index[0]

#     if lbound:
#         attrz[idx].update({'lbound':lbound})
#     if rbound:
#         attrz[idx].update({'rbound':rbound})

# def addBounds(attrz,bounds):
#     '''add bounds to attrz in place\n
#     bounds in form\n
#     bounds = {\n
#         'corr':{'lbound':0.9},\n
#         'MAE':{'rbound':0.75},\n
#         'RMSE':{'rbound':0.75},\n
#         'NSE':{'lbound':0.5},\n
#     }'''
#     [addBound(attrz,key,**kwargz) for key,kwargz in bounds.items()]

def toDF(tc) -> pd.DataFrame:
    """
    Convert the custom JSON dict back into a pandas DataFrame. inverse of deposit
    """
    jsn = deepcopy(tc) if isinstance(tc,dict) \
        else json.load(open(tc)) 
    # Each entry in 'data' has 'name' = column name, 'y' = column values
    cols = {}
    for col_entry in jsn['data']:
        col_name = col_entry['name']
        cols[col_name] = col_entry['y']  # already a list

    df = pd.DataFrame(cols)
    if 'x' in jsn:
        df.index = jsn['x']
    df.index.name = jsn.get('layout', {}).get('xaxis', {}).get('title', {}).get('text', None)

    df.attrs = jsn.get('attrz', {})
    

    return df