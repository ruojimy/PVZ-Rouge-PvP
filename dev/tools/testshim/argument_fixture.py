TRACE=[]
def seq(name,value):
    TRACE.append(name)
    return value
def capture(*args,**kwargs):
    return dict(args=list(args),kwargs=kwargs)
def run_order():
    TRACE.clear()
    result=capture(seq('first',0),*seq('star1',[1,2]),seq('after',3),*seq('star2',[4,5]),
                   x=seq('kw',6),**seq('map1',{'y':7}),**seq('map2',{'z':8}))
    return dict(result=result,trace=list(TRACE))
def run_duplicate():
    TRACE.clear()
    try:
        capture(x=seq('first',1),**seq('second',{'x':2}))
    except TypeError:
        return dict(error='TypeError',trace=list(TRACE))
    raise AssertionError('duplicate keyword was accepted')
def run_bad_mapping():
    TRACE.clear()
    try:
        capture(**seq('mapping',[(1,2)]))
    except TypeError:
        return dict(error='TypeError',trace=list(TRACE))
    raise AssertionError('non-mapping keyword spread was accepted')
