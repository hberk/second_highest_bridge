import { mount } from 'svelte';
import './styles/table.css';
import './styles/app-shell.css';
import './styles/mobile.css';
import App from './App.svelte';

export default mount(App, { target: document.getElementById('app')! });
