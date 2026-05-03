import { Component } from '@angular/core';
import { RouterOutlet } from '@angular/router';
import { AiModalsComponent } from './core/ai-modals/ai-modals.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [RouterOutlet, AiModalsComponent],
  templateUrl: './app.component.html',
})
export class AppComponent {}
