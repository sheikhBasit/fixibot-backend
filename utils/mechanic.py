from math import asin, cos, radians, sin, sqrt
from bson import ObjectId
from models.mechanic import MechanicIn, MechanicOut, MechanicUpdate
from fastapi.encoders import jsonable_encoder
from uuid import UUID

#TODO: Creation of Mechanic
async def create_mechanic(self, mechanic: MechanicIn) -> MechanicOut:
        mechanic_dict = jsonable_encoder(mechanic)
        result = await self.collection.insert_one(mechanic_dict)
        created = await self.collection.find_one({"_id": result.inserted_id})
        return MechanicOut(**created)

#TODO: Get All Mechanic
async def get_all_mechanics(self, skip: int = 0, limit: int = 100) -> list[MechanicOut]:
        cursor = self.collection.find().skip(skip).limit(limit)
        mechanics = await cursor.to_list(length=limit)
        return [MechanicOut(**m) for m in mechanics]

#TODO: Get  Mechanic by id
async def get_mechanic_by_id(self, mechanic_id: UUID) -> MechanicOut | None:
        mechanic = await self.collection.find_one({"_id": ObjectId(str(mechanic_id))})
        if mechanic:
            return MechanicOut(**mechanic)
        return None

#TODO: Updation of Mechanic
async def update_mechanic(self, mechanic_id: UUID, update_data: MechanicUpdate) -> MechanicOut | None:
        update_dict = {k: v for k, v in update_data.dict(exclude_unset=True).items()}
        if not update_dict:
            return None
        result = await self.collection.update_one(
            {"_id": ObjectId(str(mechanic_id))},
            {"$set": update_dict}
        )
        if result.modified_count == 1:
            updated = await self.collection.find_one({"_id": ObjectId(str(mechanic_id))})
            return MechanicOut(**updated)
        return None

#TODO: Deletion of Mechanic
async def delete_mechanic(self, mechanic_id: UUID) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(str(mechanic_id))})
        return result.deleted_count == 1

#TODO: Verification of Mechanic
async def set_verification_status(self, mechanic_id: UUID, verified: bool) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(str(mechanic_id))},
            {"$set": {"is_verified": verified}}
        )
        return result.modified_count == 1

#TODO: Toggling availabilty of Mechanic
async def set_availability(self, mechanic_id: UUID, is_available: bool) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(str(mechanic_id))},
            {"$set": {"is_available": is_available}}
        )
        return result.modified_count == 1

#TODO: Distance calculation method
def haversine(lon1, lat1, lon2, lat2):
    """
    Calculate the great circle distance between two points on the earth (specified in decimal degrees)
    Returns distance in kilometers
    """
    # Convert decimal degrees to radians
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # Haversine formula
    dlon = lon2 - lon1 
    dlat = lat2 - lat1 
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a)) 
    r = 6371  # Radius of Earth in km
    return c * r
