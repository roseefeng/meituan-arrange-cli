import dataclasses
from dataclasses import dataclass


@dataclass
class Itinerary:
    plan_id: str
    title: str
    member_timelines: dict
    prep_list: list

    def to_dict(self):
        return dataclasses.asdict(self)


class ItineraryGenerator:
    def generate(self, plan, scenario):
        member = "solo" if scenario == "solo" else "adult"
        companion = "child" if scenario == "family" else "companion"
        timelines = {
            member: [
                {"time": "14:40", "text": "leave with buffer"},
                {"time": "15:00", "text": plan.slots[0].name},
                {"time": "17:40", "text": plan.slots[-1].name},
            ]
        }
        if scenario != "solo":
            timelines[companion] = [
                {"time": "14:50", "text": "arrive directly at first stop"},
                {"time": "16:20", "text": "join bookstore activity"},
                {"time": "19:00", "text": "ride home together"},
            ]
        return Itinerary(
            plan_id=plan.id,
            title=plan.title,
            member_timelines=timelines,
            prep_list=["umbrella", "reservation QR", "refundable groupbuy confirmation"],
        )
