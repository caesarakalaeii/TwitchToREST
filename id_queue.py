from asyncio import Queue


class ID_Queue:
    
    known_ids = [int]
    queue = Queue()
    
    async def put(self, id:int):
        self.known_ids.append(id)
        await self.queue.put(id)
        
    async def get(self):
        id = await self.queue.get()
        self.known_ids.remove(id)
        return id
    async def is_empty(self):
        return self.queue.empty()
    
    async def contains(self, id:int):
        return id in self.known_ids
    
    async def remove(self, id):
        new_q = Queue
        if not self.contains(id):
            return
        self.known_ids.remove(id)
        while(not self.queue.empty):
            i = await self.queue.get()
            if i == id:
                continue
            new_q.put(i)
        self.queue = new_q