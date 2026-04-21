"""
input:
{
    task_id='1',
    images={
        'image_id1'='abc',
        'image_id2'='abc2'
    }
}

output:
{
    task_id='1',
    run_success=True,
    not_finished=['id1','id2'],
    msg='not finished'
}

"""
import json
import os
from datetime import datetime

import boto3
from boto3.dynamodb.conditions import Attr

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))


def _image_table():
    region = os.getenv("AWS_REGION", "us-west-1")
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", "ImageMetadata")
    session = boto3.Session(region_name=region)
    return session.resource("dynamodb").Table(table_name)


class processor:

    def __init__(self,event,context):
        self.tasks={}
        self.not_finished=[]
        self.task_id=''
        self.context=context
        self.msg=''
        self.run_success=True
        self.wait_to_write=[]
        self.writed=set()
        self.time_exhausted=False
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
            self.task_id=str(payload.get('task_id',''))
            images=payload.get('images',{})
            if not self.task_id:
                self.msg='Error when loading sqs msg: task_id is required'
                self.run_success=False
                return
            if not isinstance(images,dict):
                self.msg='Error when loading sqs msg: images should be dict'
                self.run_success=False
                return
            self.tasks={str(k):str(v) for k,v in images.items()}
        except Exception as e:
            self.msg='Error when loading sqs msg: '+str(e)
            self.run_success=False
        
    def has_enough_time(self, threshold_seconds=TIME_GUARD_SECONDS)->bool:
        if self.context is None or not hasattr(self.context,'get_remaining_time_in_millis'):
            self.msg='Error when loading lambda context: get_remaining_time_in_millis not found'
            self.run_success=False
            return False
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms

    def _resolve_user_id(self, table, image_id: str) -> str:
        start_key=None
        while True:
            scan_kwargs={
                'FilterExpression':Attr('image_id').eq(image_id),
                'ProjectionExpression':'user_id,image_id',
                'Limit':1
            }
            if start_key is not None:
                scan_kwargs['ExclusiveStartKey']=start_key
            resp=table.scan(**scan_kwargs)
            items=resp.get('Items',[])
            if items:
                return str(items[0].get('user_id',''))
            start_key=resp.get('LastEvaluatedKey')
            if not start_key:
                return ''
    
    def write_database(self)->bool:
        try:
            table=_image_table()
            now=datetime.utcnow().isoformat()
            for image_id in self.wait_to_write:
                if not self.has_enough_time():
                    self.time_exhausted=True
                    return False
                user_id=self._resolve_user_id(table,image_id)
                if not user_id:
                    raise ValueError('user_id not found for image_id: '+image_id)
                answer=self.tasks.get(image_id,'')
                table.update_item(
                    Key={'user_id':user_id,'image_id':image_id},
                    UpdateExpression='SET followup_answers = list_append(if_not_exists(followup_answers, :empty), :ans), #s = :s, updated_at = :t',
                    ExpressionAttributeNames={'#s':'status'},
                    ExpressionAttributeValues={
                        ':empty':[],
                        ':ans':[answer],
                        ':s':'complete',
                        ':t':now
                    }
                )
        except Exception as e:
            self.msg='Error when writeing to database: '+str(e)
            self.run_success=False
            return False
        return True
    
    def process(self)->None:
        self.not_finished=[]
        self.wait_to_write=[]
        task_items=list(self.tasks.items())
        if not self.has_enough_time():
            self.time_exhausted=True
            self.not_finished=[image_id for image_id,_ in task_items]
            return
        for i,(k,v) in enumerate(task_items):
            self.wait_to_write.append(k)
            if not self.run_success:
                return
            if (i+1)%100==0 or i==len(task_items)-1:
                if not self.has_enough_time():
                    self.time_exhausted=True
                    break
                #write into database
                write_ok=self.write_database()
                if write_ok:
                    for image_id in self.wait_to_write:
                        self.writed.add(image_id)
                    self.wait_to_write=[]
                elif self.time_exhausted:
                    break
                else:
                    return
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
            'task_id':self.task_id,
            'run_success':self.run_success,
            'not_finished':self.not_finished,
            'msg':self.msg
        }
        return msg


def lambda_handler(event, context):
    pro=processor(event,context)
    pro.run()
    return pro.reply()
