"""
    和 django 本身关系比较近的函数
    需要依赖 django 环境才能运行
    辅助 view 的函数
    如果都定义在 utils，容易出现 utils 里面导入 models
    models 里面导入 utils 的情况，就会报错
"""

from django.conf import settings
from django.db.models import F
from .models import Directory, File, Link, get_media_abspath
import hashlib
import uuid
import os
import re
import qrcode
import json,urllib.request#钉钉发消息
import shutil #拷贝文件
from .inspect import Scan #导入clamav检测
def handle_repetitive_file(file):
    """
        处理同名的或者重复的文件
        file: File object

        通过遍历看是否有重复路径，如果有重复，则返回带序号的 path
    """

    # 同一个用户的重名文件，与 digest 无关
    if File.objects.filter(owner=file.owner, path=file.path, name=file.name).count() > 1:
        base, ext = os.path.splitext(file.name)
        file.name = '{}_{}{}'.format(base, file.pk, ext)
        file.save()

    Link.add_one(file)
#检测文件后缀
def file_extension(path):
  file_name, extension_name = os.path.splitext(path) 
  #return os.path.splitext(path)[1] 
  return extension_name

def handle_uploaded_files(files, owner, directory):
    """
        files: 接收到来自用户上传的一组文件
        owner: 用户的 user 对象
        directory: 用户上传文件时所在的目录

        先给一个随机名字，然后一边接收，一边 hash，
        最后用 hash 值来命名文件
    """
    # import pdb; pdb.set_trace()
    media_dir = get_media_abspath() # 所有文件的绝对路径

    for file in files:

        digest = hashlib.sha1()
        temp_filename = os.path.join(media_dir, str(uuid.uuid1())) #　临时文件
        with open(temp_filename, 'wb+') as destination:

            for chunk in file.chunks(chunk_size=1024):
                destination.write(chunk)
                destination.flush()
                digest.update(chunk)

        digest = digest.hexdigest() # hash 对象转字符串
        print("打印:",digest)
        file_ext=file_extension(file.name)
        print("文件后缀名:",file_ext)
        abspath = os.path.join(media_dir, digest) # 服务器路径，用于储存
        original_file = os.path.join(media_dir, file.name) #用户保存原本文件
        print("handle打印1:",abspath)
        file = File.objects.create( # 返回 file 对象
            name = re.sub(r'[%/]', '_', file.name), # 给用户看的名字，去掉正斜杠和百分号，just in case
                                               # 亲测 mac 下，名字带正斜杠的文件无法被上传
            owner = owner,
            parent = directory, 
            digest = digest,    # 服务器上真正的名字
            path = directory.path, # 用户路径，用户给用户展示，不包含文件名
            size = file._size,


        )
     #   file_ext=file_extension(file.name)
     #   print("文件后缀名:",file_ext)

        if file_ext == ".ipa"  :
           print("iso 文件")
        
        else:
          file_ext=file_extension(file.name)
          print("文件后缀名:",file_ext)
          print("handle打印2:",file)
          ID=file.id
          qrurl=settings.QR_URL#导入settings里配置的变量
          print("打印qrurl:",qrurl)
          data=''+qrurl+''+str(ID)+''
          img2=qrcode.make(data=data)
          imgname=''+digest+'.jpg'
          print("打印图片名字:",imgname)
          img2.save('myapp/static/myapp/img/'+imgname+'')        
          fileid = File.objects.get(id=ID)
          fileid.qrcode=(imgname)
          fileid.save() 
          print("打印:",ID,data)
#clamav
#          IPs=['127.0.0.1']   #扫描主机的列表
#          scantype="multiscan_file" #指定扫描模式,支持 multiscan_file、contscan_file、scan_file
#          scanfile=temp_filename #指定扫描路径
#          i=1
#          threadnum=2   #指定启动的线程数
#          scanlist = [] #存储Scan类线程对象列表
#          for ip in IPs:
#            """将数据值带入类中，实例化对象"""
#            currp = Scan(ip,scantype,scanfile)
#            scanlist.append(currp) #追加对象到列表
#            """当达到指定的线程数或IP列表数后启动线程"""
#            if i%threadnum==0 or i==len(IPs):
#              for task in scanlist:
#                task.start() #启动线程
#              for task in scanlist:
#                task.join() #等待所有子线程退出，并输出扫描结果
#                print(task.connstr) #打印服务器连接信息
#                print(task.scanresult) #打印结果信息
#              scanlist = []   
#            i+=1

#钉钉
          url = settings.DD_URL   #url为机器人的webhook
          header = {
            "Content-Type": "application/json",
            "Charset": "UTF-8"
          }
          data = {
            "msgtype": "text",
            "text": {
            "content": "有新的文件上传哦"
             },
            "at": {
                "isAtAll": True     #@全体成员（在此可设置@特定某人）
            }
          }
          sendData = json.dumps(data)#将字典类型数据转化为json格式
          sendData = sendData.encode("utf-8") # python3的Request要求data为byte类型
          request = urllib.request.Request(url=url, data=sendData, headers=header)
          opener = urllib.request.urlopen(request)
          print(opener.read())
        os.rename(temp_filename, abspath)
        shutil.copyfile(abspath, original_file) #多一份保存原版文件
        handle_repetitive_file(file)

def set_captcha_to_session(request, captcha_text):
    """
        将 captcha_text 添加到当前用户的 session 中，
        仅在用户 cookies 中不带 sessionid 时创建 session
    """
    sessionid = settings.SESSION_COOKIE_NAME # 默认值就是 sessionid
    key = request.COOKIES.get(sessionid) # sessionid 的值
    if key is None: # 用户没有任何 sessionid
        request.session.create()
        key = request.session.session_key
        
    request.session[key] = {'captcha': ''.join(captcha_text).lower()}

def get_session_data(request, key):
    """
        根据 request 返回对应的 data dict，如果无法返回 data 则返回 {}
    """
    return request.session.get(key)

def set_session_data(request, key, value):
    """
        为 session 新增键值对
    """
    request.session.update({key: value})
    request.session.modified = True
