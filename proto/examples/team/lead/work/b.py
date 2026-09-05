"""子 B 寫的：work/b.py 提供 greet、shout。"""

def greet(name):
    return "hi, " + name


def shout(name):
    return greet(name).upper()
