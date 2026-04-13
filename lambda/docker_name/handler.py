"""
input:
{
    taskid=1,
    images={
        'image_id1'='abc',
        'image_id2'='abc2'
    }
}

output:
{
    taskid=1,
    run_success=True,
    not_finished=['id1','id2'],
    msg='not finished'
}

"""
import json

class processor:

    def __init__(self,event,context):
        self.tasks={}
        self.not_finished=[]
        self.taskid=''
        self.context=context
        self.msg=''
        self.run_success=True
        self.wait_to_write=[]
        self.writed=set()
        self.read_msg(event)
    
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
            self.taskid=str(payload.get('taskid',''))
            images=payload.get('images',{})
            if not isinstance(images,dict):
                self.msg='Error when loading sqs msg: images should be dict'
                self.run_success=False
                return
            self.tasks={str(k):str(v) for k,v in images.items()}
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
    
    def write_database(self)->bool:
        try:
            pass
        except Exception as e:
            self.msg='Error when writeing to database: '+str(e)
            self.run_success=False
            return False
        return True
    
    def process(self)->None:
        self.not_finished=[]
        self.wait_to_write=[]
        task_items=list(self.tasks.items())
        for i,(k,v) in enumerate(task_items):
            self.wait_to_write.append(k)
            if not self.run_success:
                return
            if (i+1)%100==0 or i==len(task_items)-1:
                if not self.has_enough_time():
                    break
                #write into database
                if self.write_database():
                    for image_id in self.wait_to_write:
                        self.writed.add(image_id)
                    self.wait_to_write=[]
        for image_id in self.tasks.keys():
            if image_id not in self.writed:
                self.not_finished.append(image_id)
        return

    def run(self):
        if self.run_success==False:
            return
        if len(self.tasks)>10000:
            self.run_success=False
            self.msg='unable to run'
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
            'taskid':self.taskid,
            'run_success':self.run_success,
            'not_finished':self.not_finished,
            'msg':self.msg
        }
        return msg

