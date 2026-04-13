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
class processor:

    def __init__(self,event,context):
        self.tasks={}
        self.not_finished=[]
        self.read(event)
        self.wait_to_write=[]
        self.writed=set()
    
    def read_msg(self,event:str)->None:
        #handel json msg
        pass
        
    def has_enough_time(self, threshold_seconds=60)->bool:
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms
    
    def write_database(self)->bool:
        try:
            pass
        except Exception as e:
            return False
        return True
    
    def process(self)->None:
        for i,(k,v) in enumerate(self.tasks.items()):
            self.wait_to_write.append(k)
            if i+1%100==0 or i==len(self.tasks)-1:
                if not self.has_enough_time():
                    break
                #write into database
                if self.write_database():
                    for i in self.wait_to_write:
                        self.writed.add(i)
                    self.wait_to_write=[]
            for i in self.tasks.keys():
                if self.tasks not in self.writed:
                    self.not_finished.append(id)
        return

    def run(self):
        if len(self.tasks)>10000:
            ret=(False,[],'unable to run')
        self.process()
        pass

