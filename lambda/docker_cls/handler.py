"""
input:
{
    task_id:'1',
    images:['id1','id2','id3']
}

inside:
{
    task_id:'1',
    images:{
        'image_id1':{
            question:'123?',
            label:'321',
            coordinate:(float('inf'),float('inf'))
        }
        'image_id2':{
            question:'123?',
            label:'321',
            coordinate:(float('inf'),float('inf'))
        }
    }
}

return:
{
    task_id:'1',
    run_success:True,
    not_finished:['id1','id2','id3'],
    questions:{'id4':'123?','id5':'123?'},
    msg:'not finished'

}
"""
import json

from PIL import Image
from processor import processor
class handler:

    def __init__(self,event,context):
        self.tasks={}
        self.wait_to_write=[]
        self.finished={}
        self.task_id=''
        self.context=context
        self.not_finished=[]
        self.questions={}
        self.msg=''
        self.run_success=True
        self.read_msg(event)
        pass

    def read_msg(self,event:str)->None:
        #handel json msg
        try:
            payload=event
            if isinstance(payload,str):
                payload=json.loads(payload)
            if not isinstance(payload,dict):
                self.msg='Error when loading sqs msg: event should be dict'
                self.run_success=False
                return
            self.task_id=str(payload.get('task_id',''))
            images=payload.get('images',[])
            if not isinstance(images,list):
                self.msg='Error when loading sqs msg: images should be list'
                self.run_success=False
                return
            self.tasks={str(image_id):{} for image_id in images}
        except Exception as e:
            self.msg='Error when loading sqs msg: '+str(e)
            self.run_success=False

        
    def has_enough_time(self, threshold_seconds=60)->bool:
        if self.context is None or not hasattr(self.context,'get_remaining_time_in_millis'):
            self.msg='Error when loading lambda context: get_remaining_time_in_millis not found'
            self.run_success=False
            return False
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms
    
    def loadimages(self,image_list:list[str])->list[tuple[str,Image.Image]]:
        try:
            pass
            return []
        #get s3 from database
        #load from s3
        except Exception as e:
            self.msg='Error when reading from database: '+str(e)
            self.run_success=False
            return []
    
    def write_database(self)->bool:
        try:
            pass
            return True
        except Exception as e:
            self.msg='Error when writeing to database: '+str(e)
            self.run_success=False
            return False
    
    def process(self)->None:
        waitlist=[]
        self.not_finished=[]
        self.questions={}
        self.wait_to_write=[]
        task_keys=list(self.tasks.keys())
        if not task_keys:
            return
        try:
            pro=processor()
        except Exception as e:
            self.msg='Error when loading model: '+str(e)
            self.run_success=False
            return
        #process data
        for c, key in enumerate(task_keys):
            waitlist.append(key)
            if not self.run_success:
                return
            if (c+1)%10==0 or c==len(task_keys)-1:
                if not self.has_enough_time():
                    break
                #process
                l=self.loadimages(waitlist)
                waitlist=[]
                for id,img in l:
                    try:
                        label=pro.predict(img)
                        question=pro.if_need_question(label)
                        coordinate=(float('inf'),float('inf'))
                        try:
                            coordinate=pro.getlocation(img)
                        except Exception:
                            pass
                        self.finished[id]={
                            'label':label,
                            'question':question,
                            'coordinate':coordinate,
                            'writed':False
                        }
                        self.wait_to_write.append(id)
                    except Exception as e:
                        self.msg='Error when processing image: '+str(e)
                        self.run_success=False
                        return
                #write to database
                if self.wait_to_write and self.write_database():
                    for id in self.wait_to_write:
                        if id in self.finished:
                            self.finished[id]['writed']=True
                    self.wait_to_write=[]
        for k in self.tasks.keys():
            if k not in self.finished:
                self.not_finished.append(k)
            elif not self.finished[k].get('writed'):
                self.not_finished.append(k)
            else:
                self.questions[k]=self.finished[k].get('question','')
            
        return
    
    def run(self):
        if self.run_success==False:
            return
        if len(self.tasks)>1000:
            self.run_success=False
            self.msg='Error for too much Files'
            return
        self.process()
        if self.run_success==False:
            return
        if self.not_finished:
            self.msg='not finished'
            return
        self.msg=''

    def reply(self):
        msg={
            'task_id':self.task_id,
            'run_success':self.run_success,
            'not_finished':self.not_finished,
            'questions':self.questions,
            'msg':self.msg
        }
        #pack into json
        return msg





                    
            
