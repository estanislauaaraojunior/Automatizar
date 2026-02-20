export interface DateObject {
    day: number;
    month: number;
    year: number;
}

export interface CalendarEvent {
    title: string;
    date: DateObject;
    description?: string;
}

export type DateRange = {
    startDate: DateObject;
    endDate: DateObject;
};