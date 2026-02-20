export function saveToLocalStorage(key: string, value: any): void {
    localStorage.setItem(key, JSON.stringify(value));
}

export function getFromLocalStorage<T>(key: string): T | null {
    const item = localStorage.getItem(key);
    return item ? JSON.parse(item) : null;
}

export function removeFromLocalStorage(key: string): void {
    localStorage.removeItem(key);
}