import random
import hashlib
import os.path
import sqlite3
import itertools
import pkg_resources
import trueseeing.literalquery

class Store:
  def __init__(self, path, mode='r'):
    if mode in 'rw':
      self.path = os.path.join(path, 'store.db')
      with open(self.path, mode) as _:
        pass
      self.db = sqlite3.connect(self.path)
      if mode == 'w':
        trueseeing.literalquery.Store(self.db).stage0()
    else:
      raise ArgumentError('mode: %s' % mode)

  def __enter__(self):
    self.db.__enter__()
    return self

  def __exit__(self, exc_type, exc_value, traceback):
    self.db.__exit__(exc_type, exc_value, traceback)

  def op_finalize(self):
    self.db.execute('analyze')
    trueseeing.literalquery.Store(self.db).stage1()

  def op_get(self, k):
    for t,v in self.db.execute('select t,v from ops where id=?', (k)):
      return Token(t, v)

  def op_append(self, op):
    unused_id = None
    for r in self.db.execute('select max(op) from ops'):
      if r[0] is not None:
        unused_id = r[0] + 1
      else:
        unused_id = 1
    vec = tuple([op] + op.p)
    for t, idx in zip(vec, range(len(vec))):
      t._idx = idx
      t._id = unused_id + idx
    self.db.executemany('insert into ops(op,t,v) values (?,?,?)', ((t._id, t.t, t.v) for t in vec))
    self.db.executemany('insert into ops_p(op, idx, p) values (?,?,?)', ((op._id, t._idx, t._id) for t in vec[1:]))

  def op_param_append(self, op, p):
    for r in self.db.execute('select max(idx) from ops_p where op=?', (op._id,)):
      if r[0] is not None:
        p._idx = r[0] + 1
      else:
        p._idx = 1
    self.db.execute('insert into ops_p(op, idx, p) values (?,?,?)', (op._id, p._idx, p._id))

  def op_mark_method(self, ops, method):
    self.db.executemany('insert into ops_method(op,method) values (?,?)', ((str(o._id), str(method._id)) for o in itertools.chain(ops, *(o.p for o in ops))))

  def op_mark_class(self, ops, class_, ignore_dupes=False):
    if not ignore_dupes:
      self.db.executemany('insert into ops_class(op,class) values (?,?)', ((str(o._id), str(class_._id)) for o in itertools.chain(ops, *(o.p for o in ops))))
    else:
      self.db.executemany('insert or ignore into ops_class(op,class) values (?,?)', ((str(o._id), str(class_._id)) for o in itertools.chain(ops, *(o.p for o in ops))))

  def query(self):
    return Query(self)

class Query:
  def __init__(self, store):
    self.db = store.db
