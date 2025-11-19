import { Search } from 'lucide-react';
import { Input } from './input';
import { Button } from './button';

interface SearchBarProps {
  onSearch: (query: string) => void;
}

export function SearchBar({ onSearch }: SearchBarProps) {
  return (
    <div className="w-full max-w-3xl mx-auto">
      <div className="relative">
        <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-gray-400" />
        <Input
          type="text"
          placeholder="Lostify Search Your Item Here"
          className="pl-12 pr-32 py-6 rounded-full border-2"
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onSearch(e.currentTarget.value);
            }
          }}
        />
        <Button 
          className="absolute right-2 top-1/2 -translate-y-1/2 rounded-full px-6"
          onClick={(e) => {
            const input = e.currentTarget.parentElement?.querySelector('input');
            if (input) onSearch(input.value);
          }}
        >
          Search
        </Button>
      </div>
    </div>
  );
}
