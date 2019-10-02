'''
Created on Sep 10, 2013

The module contains the definitions of State and Type that are used in IFC configuration dictionaries
@author: dli
'''

class State(object):
    NOCHANGE=0
    CREATE=1
    MODIFY=2
    DESTROY=3

class Type(object):
    DEV=0
    GRP=1
    CONN=2
    FUNC=3
    FOLDER=4
    PARAM=5
    RELATION=6
    ENCAP=7
    ENCAPASS=8
    ENCAPREL=9
    VIF=10
    CIF=11
    LIF=12
