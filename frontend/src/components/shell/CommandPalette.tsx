import React, { useEffect, useState, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { Search, Command, ArrowRight } from 'lucide-react';
import { useUIStore } from '../../stores/useUIStore';
import { useWorkspaceStore } from '../../stores/useWorkspaceStore';
import { ALL_NAV_ITEMS } from '../../constants/navigation';
import { Plant } from '../../types/tenant';

export const CommandPalette: React.FC = () => {
  const { commandPaletteOpen, setCommandPaletteOpen } = useUIStore();
  const { plants, setPlant } = useWorkspaceStore();
  const navigate = useNavigate();
  const [query, setQuery] = useState('');
  const inputRef = useRef<HTMLInputElement>(null);

  // Keyboard shortcut (Cmd+K / Ctrl+K)
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        setCommandPaletteOpen(!commandPaletteOpen);
      }
      if (e.key === 'Escape' && commandPaletteOpen) {
        setCommandPaletteOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [commandPaletteOpen, setCommandPaletteOpen]);

  // Focus input when opened
  useEffect(() => {
    if (commandPaletteOpen && inputRef.current) {
      inputRef.current.focus();
      setQuery(''); // Reset on open
    }
  }, [commandPaletteOpen]);

  if (!commandPaletteOpen) return null;

  const filteredNav = ALL_NAV_ITEMS.filter(n => n.label.toLowerCase().includes(query.toLowerCase()));
  const filteredPlants = plants.filter(p => p.name.toLowerCase().includes(query.toLowerCase()));

  const handleNavSelect = (path: string) => {
    navigate(path);
    setCommandPaletteOpen(false);
  };

  const handlePlantSelect = (plant: Plant) => {
    setPlant(plant);
    navigate(`/plants/${plant.id}/live`);
    setCommandPaletteOpen(false);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[15vh]">
      <div
        className="absolute inset-0 bg-slate-900/50 backdrop-blur-sm"
        onClick={() => setCommandPaletteOpen(false)}
      />
      <div className="relative w-full max-w-2xl bg-white rounded-xl shadow-2xl border border-slate-200 overflow-hidden flex flex-col max-h-[70vh]">

        {/* Search Input */}
        <div className="flex items-center px-4 py-3 border-b border-slate-100 gap-3">
          <Search className="h-5 w-5 text-slate-400" />
          <input
            ref={inputRef}
            type="text"
            className="flex-1 bg-transparent border-none outline-none text-slate-800 placeholder:text-slate-400"
            placeholder="Search pages, plants, tags (Type '>' for commands)..."
            value={query}
            onChange={e => setQuery(e.target.value)}
          />
          <div className="flex items-center gap-1.5">
            <kbd className="bg-slate-100 border border-slate-200 rounded px-1.5 py-0.5 text-[10px] font-mono text-slate-500">esc</kbd>
          </div>
        </div>

        {/* Results */}
        <div className="flex-1 overflow-y-auto p-2">
          {query.length > 0 && filteredNav.length === 0 && filteredPlants.length === 0 && (
            <div className="py-12 text-center text-sm text-slate-500">
              No results found for "{query}"
            </div>
          )}

          {filteredNav.length > 0 && (
            <div className="mb-4">
              <div className="px-3 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">Pages</div>
              {filteredNav.map(nav => (
                <button
                  key={nav.id}
                  onClick={() => handleNavSelect(nav.path)}
                  className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-50 rounded-lg text-sm text-slate-700 text-left transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <Command className="h-4 w-4 text-blue-500" />
                    {nav.label}
                  </div>
                  <span className="text-[10px] text-slate-400">{nav.category}</span>
                </button>
              ))}
            </div>
          )}

          {filteredPlants.length > 0 && (
            <div>
              <div className="px-3 py-1.5 text-xs font-semibold text-slate-400 uppercase tracking-wider">Plants</div>
              {filteredPlants.map(plant => (
                <button
                  key={plant.id}
                  onClick={() => handlePlantSelect(plant)}
                  className="w-full flex items-center justify-between px-3 py-2.5 hover:bg-slate-50 rounded-lg text-sm text-slate-700 text-left transition-colors"
                >
                  <div className="flex items-center gap-3">
                    <span className={`h-2 w-2 rounded-full ${plant.status === 'online' ? 'bg-emerald-500' : 'bg-amber-500'}`} />
                    {plant.name}
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-slate-400 font-mono">{plant.id}</span>
                    <ArrowRight className="h-3.5 w-3.5 text-slate-300" />
                  </div>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
