"""
input:
[
    {
        "user_id": "test_2c6c5ba6c5@example.com",
        "image_id": "229b6787-34d3-435c-bbb8-9d0c79eec148",
        "s3_key": "test_2c6c5ba6c5@example.com/229b6787-34d3-435c-bbb8-9d0c79eec148/test.jpg"
    }
]

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
import io
from datetime import datetime
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Attr

TIME_GUARD_SECONDS = int(os.getenv("LAMBDA_TIME_GUARD_SECONDS", "30"))
DEFAULT_AWS_REGION = "us-west-1"
DEFAULT_S3_BUCKET = "ee547-project-group5-ai-cloud-album"
DEFAULT_IMAGE_TABLE = "ImageMetadata"
IMAGE_REF_SEPARATOR = "#"
HANDLER_VERSION = "class-strict-2026-04-25-02"


def _session():
    region = os.getenv("AWS_REGION", DEFAULT_AWS_REGION)
    return boto3.Session(region_name=region)


def _image_table():
    table_name = os.getenv("DYNAMODB_IMAGE_TABLE", DEFAULT_IMAGE_TABLE)
    return _session().resource("dynamodb").Table(table_name)


def _s3_client():
    return _session().client("s3")


def _bucket_name():
    return os.getenv("S3_BUCKET", DEFAULT_S3_BUCKET)


def _make_image_ref(user_id: str, image_id: str) -> str:
    return f"{user_id}{IMAGE_REF_SEPARATOR}{image_id}"


def _parse_image_ref(value: str) -> tuple[str, str]:
    if IMAGE_REF_SEPARATOR in value:
        user_id, image_id = value.split(IMAGE_REF_SEPARATOR, 1)
        if user_id and image_id:
            return user_id, image_id
    return "", value


def _parse_image_input(value: str) -> tuple[str, str, str]:
    user_id, image_id = _parse_image_ref(value)
    if user_id:
        return user_id, image_id, ""
    parts = value.split("/", 2)
    if len(parts) >= 2 and parts[0] and parts[1]:
        return parts[0], parts[1], value
    return "", value, ""


class handler:

    def __init__(self,event,context):
        self.tasks={}
        self.wait_to_write=[]
        self.finished={}
        self.task_id=''
        self.context=context
        self.not_finished=[]
        self.questions={}
        self.skipped=set()
        self.failed=set()
        self.errors=[]
        self.msg=''
        self.run_success=True
        self.time_exhausted=False
        self.read_msg(event)

    def add_error(self, image_id: str, message: str)->None:
        error={
            'image_id':image_id,
            'msg':message
        }
        self.errors.append(error)
        if not self.msg:
            self.msg=message

    def read_msg(self,event:str)->None:
        #handel json msg
        try:
            payload=event
            if isinstance(payload,str):
                payload=json.loads(payload)
            if isinstance(payload,list):
                payload={'task_id':'class-batch','images':payload}
            elif isinstance(payload,dict) and isinstance(payload.get('Records'),list):
                images=[]
                task_id=str(payload.get('task_id',''))
                for record in payload.get('Records',[]):
                    body=record.get('body',record) if isinstance(record,dict) else record
                    if isinstance(body,str):
                        body=json.loads(body)
                    if isinstance(body,list):
                        images.extend(body)
                        continue
                    if isinstance(body,dict):
                        if not task_id:
                            task_id=str(body.get('task_id',''))
                        if isinstance(body.get('images'),list):
                            images.extend(body.get('images',[]))
                        elif body.get('image_id'):
                            images.append({
                                'image_id':body.get('image_id'),
                                'user_id':body.get('user_id',''),
                                's3_key':body.get('s3_key','')
                            })
                payload={'task_id':task_id or 'sqs-batch','images':images}
            elif isinstance(payload,dict) and 'body' in payload:
                body=payload.get('body')
                if isinstance(body,str):
                    body=json.loads(body)
                if isinstance(body,dict):
                    payload=body
            if isinstance(payload,dict) and 'images' not in payload and payload.get('image_id'):
                payload={
                    'task_id':str(payload.get('task_id') or payload.get('image_id')),
                    'images':[{
                        'image_id':payload.get('image_id'),
                        'user_id':payload.get('user_id',''),
                        's3_key':payload.get('s3_key','')
                    }]
                }
            if not isinstance(payload,dict):
                self.msg='Error when loading sqs msg: event should be dict'
                self.add_error('',self.msg)
                self.run_success=False
                return
            self.task_id=str(payload.get('task_id',''))
            images=payload.get('images',[])
            if not self.task_id:
                self.task_id='class-batch'
            if not isinstance(images,list):
                self.msg='Error when loading sqs msg: images should be list'
                self.add_error('',self.msg)
                self.run_success=False
                return
            self.tasks={}
            for entry in images:
                if isinstance(entry,str):
                    user_id,image_id,s3_key=_parse_image_input(entry)
                    task_info={
                        'user_id':user_id,
                        's3_key':s3_key,
                        'image_ref':entry if user_id else ''
                    }
                elif isinstance(entry,dict):
                    image_ref=str(entry.get('image_ref','')).strip()
                    ref_user_id,ref_image_id,ref_s3_key=_parse_image_input(image_ref) if image_ref else ('','','')
                    image_id=str(entry.get('image_id') or ref_image_id or '').strip()
                    user_id=str(entry.get('user_id') or ref_user_id or '').strip()
                    task_info={
                        'user_id':user_id,
                        's3_key':str(entry.get('s3_key') or ref_s3_key or '').strip(),
                        'image_ref':_make_image_ref(user_id,image_id) if user_id and image_id else image_ref
                    }
                else:
                    self.msg='Error when loading sqs msg: images must contain user_id#image_id strings or dicts'
                    self.add_error('',self.msg)
                    self.run_success=False
                    return
                if not image_id:
                    self.msg='Error when loading sqs msg: images must contain non-empty image_id'
                    self.add_error('',self.msg)
                    self.run_success=False
                    return
                self.tasks[image_id]=task_info
        except Exception as e:
            self.msg='Error when loading sqs msg: '+str(e)
            self.add_error('',self.msg)
            self.run_success=False

        
    def has_enough_time(self, threshold_seconds=TIME_GUARD_SECONDS)->bool:
        if self.context is None or not hasattr(self.context,'get_remaining_time_in_millis'):
            self.msg='Error when loading lambda context: get_remaining_time_in_millis not found'
            self.add_error('',self.msg)
            self.run_success=False
            return False
        remaining_time_ms = self.context.get_remaining_time_in_millis()
        threshold_ms = threshold_seconds * 1000
        return remaining_time_ms >= threshold_ms
    
    def loadimages(self,image_list:list[str])->list[tuple[str,object]]:
        try:
            from PIL import Image

            bucket=_bucket_name()
            table=_image_table()
            s3=_s3_client()
            images=[]
            for image_id in image_list:
                if not self.has_enough_time():
                    self.time_exhausted=True
                    return images
                record=self._resolve_record(table,image_id)
                if not self.run_success:
                    return images
                if not record:
                    self.skipped.add(image_id)
                    self.add_error(image_id,'image record not found')
                    continue
                status=str(record.get('status','')).strip()
                if status!='uploaded':
                    self.skipped.add(image_id)
                    self.add_error(image_id,'image status is not uploaded: '+status)
                    continue
                user_id=str(record.get('user_id','')).strip()
                if not user_id:
                    self.failed.add(image_id)
                    self.add_error(image_id,'user_id not found in image record')
                    continue
                if not self._update_status(table,user_id,image_id,'processing'):
                    return images
                s3_key=str(record.get('s3_key','')).strip()
                if not s3_key:
                    self._mark_failed(table,image_id,record,'s3_key not found in image record')
                    continue
                try:
                    buf=io.BytesIO()
                    s3.download_fileobj(bucket,s3_key,buf)
                    buf.seek(0)
                    img=Image.open(buf)
                    img.load()
                    images.append((image_id,img))
                except Exception as e:
                    self._mark_failed(table,image_id,record,'Error when downloading or opening image: '+str(e))
            return images
        #get s3 key from DynamoDB, then load image bytes from S3
        except Exception as e:
            self.msg='Error when reading from database: '+str(e)
            self.add_error('',self.msg)
            self.run_success=False
            return []

    def _resolve_record(self, table, image_id: str) -> dict:
        task_info=self.tasks.get(image_id,{})
        user_id=''
        if isinstance(task_info,dict):
            user_id=str(task_info.get('user_id','')).strip()
            if user_id:
                resp=table.get_item(Key={'user_id':user_id,'image_id':image_id})
                item=resp.get('Item')
                if item:
                    task_info['image_ref']=_make_image_ref(user_id,image_id)
                    return item
                if task_info.get('s3_key'):
                    task_info['image_ref']=_make_image_ref(user_id,image_id)
                    return {
                        'user_id':user_id,
                        'image_id':image_id,
                        's3_key':task_info.get('s3_key')
                    }
        start_key=None
        while True:
            scan_kwargs={
                'FilterExpression':Attr('image_id').eq(image_id),
                'ProjectionExpression':'user_id,image_id,s3_key,#s',
                'ExpressionAttributeNames':{'#s':'status'},
                'Limit':1
            }
            if start_key is not None:
                scan_kwargs['ExclusiveStartKey']=start_key
            resp=table.scan(**scan_kwargs)
            items=resp.get('Items',[])
            if items:
                found_user_id=str(items[0].get('user_id',''))
                if isinstance(task_info,dict) and found_user_id:
                    task_info['user_id']=found_user_id
                    task_info['image_ref']=_make_image_ref(found_user_id,image_id)
                return items[0]
            start_key=resp.get('LastEvaluatedKey')
            if not start_key:
                return {}

    def _resolve_user_id(self, table, image_id: str) -> str:
        record=self._resolve_record(table,image_id)
        return str(record.get('user_id','')) if record else ''

    def _image_ref_for(self, image_id: str) -> str:
        return image_id

    def _update_status(self, table, user_id: str, image_id: str, status: str) -> bool:
        try:
            table.update_item(
                Key={'user_id':user_id,'image_id':image_id},
                UpdateExpression='SET #s = :s, updated_at = :t',
                ExpressionAttributeNames={'#s':'status'},
                ExpressionAttributeValues={
                    ':s':status,
                    ':t':datetime.utcnow().isoformat()
                }
            )
            return True
        except Exception as e:
            self.msg='Error when updating status: '+str(e)
            self.add_error(image_id,self.msg)
            self.run_success=False
            return False

    def _mark_failed(self, table, image_id: str, record: dict, reason: str='failed') -> None:
        user_id=str(record.get('user_id','')).strip()
        if user_id:
            self._update_status(table,user_id,image_id,'failed')
        self.failed.add(image_id)
        self.add_error(image_id,reason)

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
                status='done'
                location=self._normalize_location(result.get('coordinate'))
                record=self._resolve_record(table,image_id)
                user_id=str(record.get('user_id','')) if record else ''
                if not user_id:
                    raise ValueError('user_id not found for image_id: '+image_id)
                task_info=self.tasks.get(image_id,{})
                if isinstance(task_info,dict):
                    task_info['user_id']=user_id
                    task_info['image_ref']=_make_image_ref(user_id,image_id)
                table.update_item(
                    Key={'user_id':user_id,'image_id':image_id},
                    UpdateExpression='SET label = :l, #s = :s, #loc = :loc, followup_questions = :q, updated_at = :t',
                    ExpressionAttributeNames={'#s':'status','#loc':'location'},
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
            self.add_error('',self.msg)
            self.run_success=False
            return False
    
    def process(self)->None:
        waitlist=[]
        self.not_finished=[]
        self.questions={}
        self.wait_to_write=[]
        task_keys=list(self.tasks.keys())
        if not task_keys:
            self.msg='Error when loading sqs msg: no images provided'
            self.add_error('',self.msg)
            self.run_success=False
            return
        if not self.has_enough_time():
            self.time_exhausted=True
            self.add_error('', 'not enough lambda time before processing')
            self.not_finished=[self._image_ref_for(k) for k in task_keys]
            return
        try:
            from processor import processor

            pro=processor()
        except Exception as e:
            self.msg='Error when loading model: '+str(e)
            self.add_error('',self.msg)
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
                    self.add_error('', 'not enough lambda time before image batch')
                    break
                #process
                l=self.loadimages(waitlist)
                waitlist=[]
                for id,img in l:
                    if not self.has_enough_time():
                        self.time_exhausted=True
                        self.add_error(id, 'not enough lambda time before image processing')
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
                        table=_image_table()
                        record=self._resolve_record(table,id)
                        self._mark_failed(table,id,record,'Error when processing image: '+str(e))
                        continue
                if not self.run_success:
                    break
                #write to database
                if not self.has_enough_time():
                    self.time_exhausted=True
                    self.add_error('', 'not enough lambda time before database write')
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
            if k in self.skipped or k in self.failed:
                continue
            if k not in self.finished:
                self.not_finished.append(self._image_ref_for(k))
            elif not self.finished[k].get('writed'):
                self.not_finished.append(self._image_ref_for(k))
            else:
                self.questions[self._image_ref_for(k)]=self.finished[k].get('question','')
            
        return
    
    def run(self):
        if self.run_success==False:
            return
        if len(self.tasks)>1000:
            self.run_success=False
            self.msg='Error for too much Files'
            self.add_error('',self.msg)
            return
        self.process()
        if self.run_success==False:
            return
        if self.not_finished:
            self.run_success=False
            self.msg='not finished'
            self.add_error('', 'not finished: '+','.join(self.not_finished))
            return
        if self.skipped or self.failed:
            self.run_success=False
            parts=[]
            if self.skipped:
                parts.append('skipped: '+','.join(sorted(self.skipped)))
            if self.failed:
                parts.append('failed: '+','.join(sorted(self.failed)))
            self.msg='; '.join(parts)
            return
        if self.errors:
            self.run_success=False
            self.msg=self.msg or 'errors happened'
            return
        self.msg=''

    def reply(self):
        msg={
            'version':HANDLER_VERSION,
            'task_id':self.task_id,
            'run_success':self.run_success,
            'not_finished':self.not_finished,
            'skipped':sorted(self.skipped),
            'failed':sorted(self.failed),
            'questions':self.questions,
            'errors':self.errors,
            'msg':self.msg
        }
        #pack into json
        return msg


def lambda_handler(event, context):
    pro=handler(event,context)
    pro.run()
    reply=pro.reply()
    print(json.dumps(reply, default=str))
    return reply



                    
            
