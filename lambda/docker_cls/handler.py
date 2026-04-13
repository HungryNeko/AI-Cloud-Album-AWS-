"""
input:
{
    task_id='1',
    images=['id1','id2','id3']
}

inside:
{
    task_id='1',
    images={
        'image_id1'={
            question='123?',
            label='321',
            coordinate=(float('inf'),float('inf'))
        }
        'image_id2'={
            question='123?',
            label='321',
            coordinate=(float('inf'),float('inf'))
        }
    }
}

return:
{
    task_id='1',
    run_success=True,
    not_finnished=['id1','id2','id3'],
    questions={'id4':'123?','id5':'123?'},
    msg='not finished'

}
"""
from collections import deque

from PIL import Image
from processor import processor
class handler:

    def __init__(self,event,context):
        self.tasks={}
        self.wait_to_write=[]
        self.finished={}
        self.task_id=''
        self.read_msg(event)
        self.context=context
        self.not_finished=[]
        pass

    def read_msg(self,event:str)->None:
        #handel json msg
        pass
        
    def has_enough_time(self, threshold_seconds=60)->bool:
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms
    
    def loadimages(self,image_list:list[str])->list[tuple[str,Image.Image]]:
        #get s3 from database
        #load from s3
        pass
    
    def write_database(self)->bool:
        try:
            pass
        except Exception as e:
            return False
        return True
    
    def process(self)->None:
        waitlist=[]
        pro=processor()
        #process data
        for c, (key, value) in enumerate(self.tasks.items()):
            waitlist.append(key)
            if c+1%10==0 or c==len(self.tasks)-1:
                if not self.has_enough_time():
                    break
                #process
                l=self.loadimages(waitlist)
                waitlist=[]
                for id,img in l:
                    label=pro.predict(img)
                    question=pro.if_need_question(label)
                    coordinate=pro.getlocation(img)
                    self.finished[id]['label']=label
                    self.finished[id]['question']=question
                    self.finished[id]['coordinate']=coordinate
                    self.finished[id]['writed']=False
                    self.wait_to_write.append(id)
                #write to database
                if self.write_database():
                    for id in self.wait_to_write:
                        self.finished[id]['writed']=True
        for k in self.tasks.keys():
            if k not in self.finished:
                self.not_finished.append(k)
            elif not self.finished[k]['writed']:
                self.not_finished.append(k)
            else:
                self.questions[k]=self.finished[k]['question']
            
        return
    
    def run(self):
        if len(self.tasks)>1000:
            ret=(False,[],'unable to run, too much files',{})
        self.process()
        if self.not_finished:
            ret=(True,self.not_finished,'not finished',self.questions)
        ret=(True,[],'finished',self.quesionts)
        #write into json and return
        pass





                    
            