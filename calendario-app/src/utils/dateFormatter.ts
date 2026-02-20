export function formatDate(date: Date): string {
    const options: Intl.DateTimeFormatOptions = { 
        year: 'numeric', 
        month: 'long', 
        day: 'numeric' 
    };
    return new Intl.DateTimeFormat('pt-BR', options).format(date);
}

export function parseDate(dateString: string): Date | null {
    const parsedDate = new Date(dateString);
    return isNaN(parsedDate.getTime()) ? null : parsedDate;
}