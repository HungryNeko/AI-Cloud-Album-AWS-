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
import math
import os
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr
from PIL import Image
from processor import processor

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))


def _image_table():
    region = os.getenv("AWS_REGION", "us-west-1")
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", "ImageMetadata")
    session = boto3.Session(region_name=region)
    return session.resource("dynamodb").Table(table_name)


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
        self.time_exhausted=False
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
            if not self.task_id:
                self.msg='Error when loading sqs msg: task_id is required'
                self.run_success=False
                return
            if not isinstance(images,list):
                self.msg='Error when loading sqs msg: images should be list'
                self.run_success=False
                return
            self.tasks={}
            for entry in images:
                if not isinstance(entry,str) or not entry:
                    self.msg='Error when loading sqs msg: images must contain non-empty image_id strings'
                    self.run_success=False
                    return
                self.tasks[entry]={}
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

    def _resolve_user_id(self, table, image_id: str) -> str:
        task_info=self.tasks.get(image_id,{})
        if isinstance(task_info,dict):
            user_id=str(task_info.get('user_id','')).strip()
            if user_id:
                return user_id
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

    def _normalize_location(self, coordinate):
        if not isinstance(coordinate,(tuple,list)) or len(coordinate)!=2:
            return None
        try:
            lat=float(coordinate[0])
            lng=float(coordinate[1])
        except (TypeError,ValueError):
            return None
        if not math.isfinite(lat) or not math.isfinite(lng):
            return None
        return {
            'lat':Decimal(str(lat)),
            'lng':Decimal(str(lng))
        }
    
    def write_database(self)->bool:
        try:
            table=_image_table()
            now=datetime.utcnow().isoformat()
            for image_id in self.wait_to_write:
                if not self.has_enough_time():
                    self.time_exhausted=True
                    return False
                result=self.finished.get(image_id,{})
                label=str(result.get('label',''))
                question=str(result.get('question','') or '')
                status='needs_followup' if question else 'complete'
                location=self._normalize_location(result.get('coordinate'))
                user_id=self._resolve_user_id(table,image_id)
                if not user_id:
                    raise ValueError('user_id not found for image_id: '+image_id)
                table.update_item(
                    Key={'user_id':user_id,'image_id':image_id},
                    UpdateExpression='SET label = :l, #s = :s, location = :loc, followup_questions = :q, updated_at = :t',
                    ExpressionAttributeNames={'#s':'status'},
                    ExpressionAttributeValues={
                        ':l':label,
                        ':s':status,
                        ':loc':location,
                        ':q':[question] if question else [],
                        ':t':now
                    }
                )
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
        if not self.has_enough_time():
            self.time_exhausted=True
            self.not_finished=task_keys
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
                    self.time_exhausted=True
                    break
                #process
                l=self.loadimages(waitlist)
                waitlist=[]
                for id,img in l:
                    if not self.has_enough_time():
                        self.time_exhausted=True
                        break
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
                if not self.run_success:
                    break
                #write to database
                if not self.has_enough_time():
                    self.time_exhausted=True
                    break
                if self.wait_to_write:
                    writed_ok=self.write_database()
                    if writed_ok:
                        for id in self.wait_to_write:
                            if id in self.finished:
                                self.finished[id]['writed']=True
                        self.wait_to_write=[]
                    elif self.time_exhausted:
                        break
                    else:
                        return
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


def lambda_handler(event, context):
    pro=handler(event,context)
    pro.run()
    return pro.reply()



                    
            
