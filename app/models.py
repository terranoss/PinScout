"""Data schema for a single scraped Google Maps listing.

Defines the PinScout export field set and ordered Excel/CSV column headers.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class Listing(BaseModel):
    id: Optional[int] = None
    keyword: Optional[str] = Field(default=None, alias="Keyword")

    name: Optional[str] = None
    full_address: Optional[str] = None
    street_address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    zip: Optional[str] = None
    plus_code: Optional[str] = None

    website: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    facebook: Optional[str] = None
    twitter: Optional[str] = None
    instagram: Optional[str] = None
    youtube: Optional[str] = None
    linkedin: Optional[str] = None
    tiktok: Optional[str] = None
    pinterest: Optional[str] = None
    google_plus: Optional[str] = None

    latitude: Optional[float] = None
    longitude: Optional[float] = None

    # Exported as "Verification_Text". Presence of "Claim this business"
    # means the listing is UNCLAIMED. Kept as raw text rather than a bool.
    verification_text: Optional[str] = None

    category: Optional[str] = None
    rating: Optional[float] = None
    review_count: Optional[int] = None
    stars_5: Optional[int] = None
    stars_4: Optional[int] = None
    stars_3: Optional[int] = None
    stars_2: Optional[int] = None
    stars_1: Optional[int] = None

    top_image_url: Optional[str] = None
    sub_title: Optional[str] = None
    pricing: Optional[str] = None
    description: Optional[str] = None
    amenities: Optional[str] = None
    summary: Optional[str] = None

    hours: Optional[str] = None            # e.g. "Open · Closes 12 am"
    hours_info: Optional[str] = None
    monday: Optional[str] = None
    tuesday: Optional[str] = None
    wednesday: Optional[str] = None
    thursday: Optional[str] = None
    friday: Optional[str] = None
    saturday: Optional[str] = None
    sunday: Optional[str] = None

    external_urls: Optional[str] = None
    photo_tags: Optional[str] = None
    menu_url: Optional[str] = None
    services: Optional[str] = None
    located_in: Optional[str] = None
    attributes: Optional[str] = None

    maps_url: Optional[str] = None
    saved_image_name: Optional[str] = Field(default=None, alias="Saved_Image_Name")
    sstatus: Optional[str] = None

    class Config:
        validate_assignment = False
        populate_by_name = True


# Ordered Excel/CSV export column headers.
EXPORT_COLUMN_ORDER = [
    "id", "Keyword", "Name", "Full_Address", "Street_Address", "City",
    "State", "Zip", "Plus_Code", "Website", "Phone", "Email", "Facebook",
    "Twitter", "Instagram", "Youtube", "LinkedIn", "Tiktok", "Pinterest",
    "GooglePlus", "Lat", "Lng", "Verification_Text", "Category", "Rating",
    "Reviews", "5_Stars", "4_Stars", "3_Stars", "2_Stars", "1_Stars",
    "Top_Image_URL", "Sub_Title", "Pricing", "Description", "Amenities",
    "Summary", "Hours", "Hours_Info", "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday", "External_Urls",
    "Photo_Tags", "Menu_Url", "Services", "Located_in", "Attributes",
    "URL", "Saved_Image_Name", "Status",
]

# Maps internal snake_case field names to export header names.
FIELD_TO_EXPORT_HEADER = {
    "id": "id",
    "keyword": "Keyword",
    "name": "Name",
    "full_address": "Full_Address",
    "street_address": "Street_Address",
    "city": "City",
    "state": "State",
    "zip": "Zip",
    "plus_code": "Plus_Code",
    "website": "Website",
    "phone": "Phone",
    "email": "Email",
    "facebook": "Facebook",
    "twitter": "Twitter",
    "instagram": "Instagram",
    "youtube": "Youtube",
    "linkedin": "LinkedIn",
    "tiktok": "Tiktok",
    "pinterest": "Pinterest",
    "google_plus": "GooglePlus",
    "latitude": "Lat",
    "longitude": "Lng",
    "verification_text": "Verification_Text",
    "category": "Category",
    "rating": "Rating",
    "review_count": "Reviews",
    "stars_5": "5_Stars",
    "stars_4": "4_Stars",
    "stars_3": "3_Stars",
    "stars_2": "2_Stars",
    "stars_1": "1_Stars",
    "top_image_url": "Top_Image_URL",
    "sub_title": "Sub_Title",
    "pricing": "Pricing",
    "description": "Description",
    "amenities": "Amenities",
    "summary": "Summary",
    "hours": "Hours",
    "hours_info": "Hours_Info",
    "monday": "Monday",
    "tuesday": "Tuesday",
    "wednesday": "Wednesday",
    "thursday": "Thursday",
    "friday": "Friday",
    "saturday": "Saturday",
    "sunday": "Sunday",
    "external_urls": "External_Urls",
    "photo_tags": "Photo_Tags",
    "menu_url": "Menu_Url",
    "services": "Services",
    "located_in": "Located_in",
    "attributes": "Attributes",
    "maps_url": "URL",
    "saved_image_name": "Saved_Image_Name",
    "sstatus": "Status",
}
