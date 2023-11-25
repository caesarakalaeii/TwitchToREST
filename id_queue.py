from asyncio import Queue


class ID_Queue:
    
    known_ids = [(int, str)]
    queue = Queue()
    
    async def put(self, ids:int, referral):
        self.known_ids.append(ids)
        await self.queue.put((ids, referral))
        
    async def get(self):
        ids, ref = await self.queue.get()
        self.known_ids.remove(ids)
        return ids, ref
    
    async def is_empty(self):
        return self.queue.empty()
    
    async def contains(self, ids:int):
        return ids in self.known_ids
    
    async def remove(self, ids):
        new_q = Queue
        if not self.contains(ids):
            return
        self.known_ids.remove(ids)
        while(not self.queue.empty):
            i, ref = await self.queue.get()
            if i == ids:
                continue
            new_q.put((i, ref))
        self.queue = new_q