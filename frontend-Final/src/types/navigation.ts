import { UserRole } from './auth';

export type NavCategory = 'OVERVIEW' | 'OPERATIONS' | 'ENGINEERING' | 'ADMIN';

export interface NavItem {
  id: string;
  label: string;
  icon: string; // lucide icon name
  path: string;
  category: NavCategory;
  badge?: number;
  requiredRoles?: UserRole[];
}

export interface NavGroup {
  category: NavCategory;
  items: NavItem[];
}
