'use client';

import { useState } from 'react';
import { SearchBar } from '../components/SearchBar';
import { Button } from '../components/button';
import { PlusCircle, Package } from 'lucide-react';


export default function Home() {
  const [searchQuery, setSearchQuery] = useState('');

  const handleSearch = (query: string) => {
    setSearchQuery(query);
    console.log('Searching for:', query);
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b">
        <div className="container mx-auto px-4 py-6">
          <div className="flex items-center justify-between mb-8">
            <div className="flex items-center gap-3">
              <Package className="h-8 w-8 text-blue-600" />
              <h1 className="text-blue-600">Lost & Found</h1>
            </div>
            <Button className="gap-2">
              <PlusCircle className="h-5 w-5" />
              Report Item
            </Button>
          </div>

          <SearchBar onSearch={handleSearch} />
        </div>
      </header>



      {/* Footer */}
      <footer className="bg-white border-t mt-16">
        <div className="container mx-auto px-4 py-8 text-center text-gray-500">
          <p>Lost & Found - Helping reunite people with their belongings</p>
        </div>
      </footer>

    </div>
  );
}



