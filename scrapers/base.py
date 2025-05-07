from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any
from datetime import datetime

class RentalScraper(ABC):
    @abstractmethod
    def scrape(self, existing_listings: List[Dict]) -> Tuple[List[Dict], List[Dict], List[Dict], List[Dict]]:
        """
        Scrape website and return tuple of:
        (all_listings, new_listings, removed_listings, reactivated_listings)
        """
        pass

    def create_listing(self, **kwargs) -> Dict[str, Any]:
        """Create a standard listing dictionary"""
        return {
            'address': kwargs.get('address'),
            'url': kwargs.get('url'),
            'price': kwargs.get('price', 'N/A'),
            'size': kwargs.get('size'),
            'rooms': kwargs.get('rooms'),
            'available': kwargs.get('available'),
            'image_url': kwargs.get('image_url'),
            'active': True,
            'source': self.__class__.__name__
        }
