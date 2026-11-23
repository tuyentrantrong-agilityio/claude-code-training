// Placeholder session until auth exists; replaced by GET /api/v1/me in T10.
export type Role = 'owner' | 'member';

export interface SessionUser {
  name: string;
  email: string;
}

export interface SessionOrg {
  name: string;
}

export const placeholderUser: SessionUser = { name: 'Alex Rivera', email: 'alex@example.com' };
export const placeholderOrg: SessionOrg = { name: 'Northwind Studio' };
export const placeholderRole: Role = 'owner';
