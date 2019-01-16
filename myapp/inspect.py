# -*- coding: utf-8 -*-
#python3 代码,查毒
import time
import pyclamd
from threading import Thread
class Scan(Thread): #继承多线程Thread类
  def __init__ (self,IP,scan_type,file):
    """构造方法"""
    Thread.__init__(self)
    self.IP = IP
    self.scan_type=scan_type
    self.file = file
    self.connstr=""
    self.scanresult=""
  def run(self):
    """多进程run方法"""
    try:
      cd = pyclamd.ClamdNetworkSocket(self.IP,3310)
      """探测连通性"""
      if cd.ping():
        self.connstr=self.IP+" connection [OK]"
        """重载clamd病毒特征库"""
        cd.reload()
        """判断扫描模式"""
        if self.scan_type=="contscan_file":
          self.scanresult="{0}\n".format(cd.contscan_file(self.file))
        elif self.scan_type=="multiscan_file":
          self.scanresult="{0}\n".format(cd.multiscan_file(self.file))
        elif self.scan_type=="scan_file":
          self.scanresult="{0}\n".format(cd.scan_file(self.file))
        time.sleep(1)
      else:
        self.connstr=self.IP+" ping error,exit"
        return
    except Exception as e:
      self.connstr=self.IP+" "+str(e)
