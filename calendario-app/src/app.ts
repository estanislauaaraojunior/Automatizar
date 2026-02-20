import { Calendar } from './components/Calendar';
import { DatePicker } from './components/DatePicker';

const app = () => {
    const calendar = new Calendar();
    const datePicker = new DatePicker();

    calendar.render();
    datePicker.open();

    datePicker.onDateSelected = (date) => {
        calendar.selectDate(date);
        datePicker.saveDate(date);
    };
};

app();