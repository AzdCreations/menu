export type Language = 'ru' | 'uz';

export type User = {
  id: number;
  phone: string;
  name: string;
  language: Language;
  is_specialist: boolean;
  is_staff: boolean;
  status: 'active' | 'blocked' | 'deleted';
  pd_consent: boolean;
  created_at: string;
};

export type AuthResponse = { access: string; refresh: string; user: User };

export type BookingField = {
  key: string;
  label_ru: string;
  label_uz: string;
  type: 'text' | 'select' | 'bool';
  options?: string[];
  required?: boolean;
};

export type Category = {
  id: number;
  name: string;
  specialist_name: string;
  name_uz: string;
  name_ru: string;
  specialist_name_uz: string;
  specialist_name_ru: string;
  icon: string;
  order: number;
  is_active: boolean;
  booking_fields: BookingField[];
};

export type Photo = { id: number; image: string; order: number };

export type VenueHours = { weekday: number; start: string | null; end: string | null; is_day_off: boolean };

export type PublicService = { id: number; name: string; duration_minutes: number; price: number | null; price_from: boolean };

export type PublicSpecialist = { id: number; name: string; photo: string | null; bio: string; services: PublicService[] };

export type VenueListItem = {
  id: number;
  category: number;
  name: string;
  address: string;
  lat: string;
  lng: string;
  phone: string;
  cover: string | null;
  distance_km: number | null;
};

export type VenueDetail = VenueListItem & {
  photos: Photo[];
  hours: VenueHours[];
  specialists: PublicSpecialist[];
  specialist_name: string;
  booking_fields: BookingField[];
};

export type VenueStatus = 'pending' | 'approved' | 'rejected' | 'blocked' | 'closed';

export type OwnVenue = {
  id: number;
  category: number;
  name: string;
  address: string;
  lat: string;
  lng: string;
  phone: string;
  status: VenueStatus;
  decision_reason: string;
  photos: Photo[];
  hours: VenueHours[];
  is_owner: boolean;
  created_at: string;
  duplicates?: { id: number; name: string; address: string }[];
};

export type Service = PublicService & { is_active: boolean };

export type WorkingHours = { weekday: number; start: string; end: string; breaks: { start: string; end: string }[] };

export type MembershipStatus = 'pending' | 'accepted' | 'rejected' | 'left' | 'removed';

export type Membership = {
  id: number;
  venue: { id: number; name: string; address: string; status: VenueStatus; category: number; owner: number };
  status: MembershipStatus;
  is_owner: boolean;
  public_name: string;
  display_name: string;
  photo: string | null;
  bio: string;
  auto_confirm: boolean;
  slot_step_minutes: number;
  min_lead_minutes: number;
  horizon_days: number;
  buffer_minutes: number;
  services: Service[];
  working_hours: WorkingHours[];
};

export type Member = { id: number; name: string; phone: string; status: MembershipStatus; is_owner: boolean; created_at: string };

export type ScheduleException = {
  id: number;
  date_from: string;
  date_to: string;
  kind: 'day_off' | 'custom';
  start: string | null;
  end: string | null;
};

export type BookingStatus =
  | 'pending'
  | 'confirmed'
  | 'rejected'
  | 'expired'
  | 'cancelled_client'
  | 'cancelled_specialist'
  | 'completed'
  | 'no_show';

export type Booking = {
  id: number;
  kind: 'booking' | 'block';
  source: 'app' | 'manual';
  status: BookingStatus;
  status_label: string;
  status_reason: string;
  venue: number;
  venue_name: string;
  venue_address: string;
  venue_phone: string;
  membership: number;
  specialist_name: string;
  service: number | null;
  service_name: string;
  price: number | null;
  duration_minutes: number;
  start: string;
  end: string;
  comment: string;
  extra: Record<string, unknown>;
  respond_by: string | null;
  created_at: string;
  client_name?: string;
  client_phone?: string;
};

export type Paginated<T> = { count: number; next: string | null; previous: string | null; results: T[] };

export type AppNotification = {
  id: number;
  type: string;
  title: string;
  body: string;
  data: Record<string, unknown>;
  is_read: boolean;
  created_at: string;
};
