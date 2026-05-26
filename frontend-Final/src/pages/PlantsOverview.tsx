import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Factory,
  Search,
  MapPin,
  Activity,
  AlertTriangle,
  CheckCircle2,
  XCircle,
  MoreVertical,
  ChevronRight,
  Filter
} from 'lucide-react';
import { usePlants, usePlantSummary, Plant } from '../api/hooks/usePlants';
import { useWorkspaceStore } from '../stores/useWorkspaceStore';

// Individual Plant Card Component
const PlantCard = ({ plant }: { plant: Plant }) => {
  const navigate = useNavigate();
  const setPlant = useWorkspaceStore(state => state.setPlant);

  // Fetch real-time summary for this plant
  const { data: summary, isLoading } = usePlantSummary(plant.plant_id);

  const isOnline = plant.is_active;

  const handleEnterDashboard = () => {
    // We map the backend plant format to the frontend workspace store format
    setPlant({
      id: plant.plant_id,
      name: plant.name,
      location: plant.location,
      status: isOnline ? 'online' : 'offline',
      orgId: '',
      plantGroupId: ''
    });
    navigate(`/plants/${plant.plant_id}/live`);
  };

  return (
    <div className="bg-white rounded-2xl border border-slate-200 overflow-hidden shadow-sm hover:shadow-xl transition-all duration-300 group flex flex-col h-full relative">

      {/* Top Banner / Status Line */}
      <div className={`h-2 w-full ${isOnline ? 'bg-emerald-500' : 'bg-slate-300'}`} />

      <div className="p-6 flex-1 flex flex-col">
        {/* Header */}
        <div className="flex justify-between items-start mb-4">
          <div className="flex items-center gap-3">
            <div className={`p-3 rounded-xl ${isOnline ? 'bg-emerald-50 text-emerald-600' : 'bg-slate-100 text-slate-500'}`}>
              <Factory className="h-6 w-6" />
            </div>
            <div>
              <h3 className="font-bold text-slate-800 text-lg group-hover:text-blue-600 transition-colors">
                {plant.name}
              </h3>
              <p className="text-xs text-slate-500 flex items-center gap-1 mt-1">
                <MapPin className="h-3 w-3" /> {plant.location}
              </p>
            </div>
          </div>
          <button className="text-slate-400 hover:text-slate-600 p-1 rounded-full hover:bg-slate-100 transition-colors">
            <MoreVertical className="h-4 w-4" />
          </button>
        </div>

        {/* Status Pills */}
        <div className="flex gap-2 mb-6">
          <span className={`inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border ${isOnline ? 'bg-emerald-50 border-emerald-200 text-emerald-700' : 'bg-slate-50 border-slate-200 text-slate-600'}`}>
            {isOnline ? <CheckCircle2 className="h-3 w-3" /> : <XCircle className="h-3 w-3" />}
            {isOnline ? 'Online' : 'Offline'}
          </span>
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full text-xs font-medium border bg-blue-50 border-blue-200 text-blue-700">
            {plant.plant_type.toUpperCase()}
          </span>
        </div>

        {/* Real-time KPI Stats */}
        <div className="grid grid-cols-2 gap-4 mb-6 flex-1">
          <div className="bg-slate-50 p-3 rounded-xl border border-slate-100 flex flex-col justify-center">
            <span className="text-xs text-slate-500 font-medium mb-1 flex items-center gap-1">
              <Activity className="h-3 w-3" /> Active Tags
            </span>
            <span className="text-xl font-bold text-slate-800">
              {isLoading ? '...' : summary?.active_tags?.toLocaleString() || '0'}
            </span>
          </div>

          <div className={`p-3 rounded-xl border flex flex-col justify-center transition-colors ${summary?.critical_alarms && summary.critical_alarms > 0 ? 'bg-red-50 border-red-100' : 'bg-slate-50 border-slate-100'}`}>
            <span className={`text-xs font-medium mb-1 flex items-center gap-1 ${summary?.critical_alarms && summary.critical_alarms > 0 ? 'text-red-600' : 'text-slate-500'}`}>
              <AlertTriangle className="h-3 w-3" /> Critical Alarms
            </span>
            <span className={`text-xl font-bold ${summary?.critical_alarms && summary.critical_alarms > 0 ? 'text-red-700' : 'text-slate-800'}`}>
              {isLoading ? '...' : summary?.critical_alarms?.toLocaleString() || '0'}
            </span>
          </div>
        </div>

        {/* Action Button */}
        <button
          onClick={handleEnterDashboard}
          className="w-full mt-auto bg-white border border-slate-200 hover:border-blue-300 hover:bg-blue-50 text-blue-600 font-semibold py-2.5 rounded-xl flex items-center justify-center gap-2 transition-all duration-300 group-hover:bg-blue-600 group-hover:text-white"
        >
          View Dashboard
          <ChevronRight className="h-4 w-4 transform group-hover:translate-x-1 transition-transform" />
        </button>
      </div>
    </div>
  );
};

export default function PlantsOverview() {
  const { data: plantsData, isLoading, isError } = usePlants();
  const [searchTerm, setSearchTerm] = useState('');

  const plants = plantsData?.data || [];

  // Filter logic
  const filteredPlants = plants.filter(p =>
    p.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.location.toLowerCase().includes(searchTerm.toLowerCase()) ||
    p.plant_id.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="flex flex-col gap-8 pb-12">
      {/* Header Section */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold text-slate-900 tracking-tight">Plants Overview</h1>
          <p className="text-slate-500 mt-1">Monitor and manage all connected industrial facilities across your organization.</p>
        </div>
        <button className="bg-blue-600 hover:bg-blue-700 text-white px-5 py-2.5 rounded-xl font-medium shadow-sm shadow-blue-200 transition-colors flex items-center gap-2">
          <Factory className="h-4 w-4" /> Add New Plant
        </button>
      </div>

      {/* Toolbar / Filters */}
      <div className="bg-white p-4 rounded-2xl border border-slate-200 shadow-sm flex flex-col md:flex-row gap-4 justify-between items-center">
        <div className="relative w-full md:w-96">
          <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
            <Search className="h-4 w-4 text-slate-400" />
          </div>
          <input
            type="text"
            className="block w-full pl-10 pr-3 py-2.5 border border-slate-200 rounded-xl leading-5 bg-slate-50 placeholder-slate-400 focus:outline-none focus:bg-white focus:ring-2 focus:ring-blue-500 focus:border-blue-500 sm:text-sm transition-colors"
            placeholder="Search plants by name, ID, or location..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
          />
        </div>

        <div className="flex gap-3 w-full md:w-auto">
          <button className="px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors">
            <Filter className="h-4 w-4 text-slate-400" /> Status: All
          </button>
          <button className="px-4 py-2 bg-white border border-slate-200 rounded-xl text-sm font-medium text-slate-700 hover:bg-slate-50 flex items-center gap-2 transition-colors">
            <MapPin className="h-4 w-4 text-slate-400" /> Location: All
          </button>
        </div>
      </div>

      {/* Grid Content */}
      {isLoading ? (
        <div className="flex justify-center items-center py-20">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
        </div>
      ) : isError ? (
        <div className="bg-red-50 text-red-600 p-6 rounded-2xl border border-red-100 flex items-center justify-center">
          Failed to load plants from the server.
        </div>
      ) : filteredPlants.length === 0 ? (
        <div className="bg-slate-50 border border-slate-200 border-dashed rounded-2xl p-12 flex flex-col items-center justify-center text-center">
          <div className="h-12 w-12 bg-slate-100 rounded-full flex items-center justify-center mb-4">
            <Factory className="h-6 w-6 text-slate-400" />
          </div>
          <h3 className="text-lg font-medium text-slate-900">No plants found</h3>
          <p className="text-slate-500 mt-1 max-w-sm">No plants match your current search criteria. Try adjusting your filters.</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {filteredPlants.map(plant => (
            <PlantCard key={plant.plant_id} plant={plant} />
          ))}
        </div>
      )}
    </div>
  );
}
