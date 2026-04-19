import { Component } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';

interface ResourceItem {
  title: string;
  type: 'video' | 'notes' | 'visual';
  topic: string;
  desc: string;
  link: string;
}

const RESOURCE_ITEMS: ResourceItem[] = [
  {
    title: "Striver's A2Z Roadmap",
    type: 'video',
    topic: 'Full DSA',
    desc: 'The definitive video series for mastering algorithms from beginner to interview-ready.',
    link: 'https://www.youtube.com/playlist?list=PLgUwDviBIf0p-INQC6rMuzsSmdZ77EcrH',
  },
  {
    title: 'VisuAlgo Visualizer',
    type: 'visual',
    topic: 'Concepts',
    desc: 'Interactive animations of data structures. Use this to see how nodes move in real-time.',
    link: 'https://visualgo.net/en',
  },
  {
    title: 'Supreme DSA Notes',
    type: 'notes',
    topic: 'Handwritten',
    desc: 'Detailed Google Drive/GitHub notes covering core concepts with diagrams and code.',
    link: 'https://github.com/Ujjwal2327/DSA-SUPREME',
  },
  {
    title: 'Algorithm Visualizer',
    type: 'visual',
    topic: 'Code-Sync',
    desc: 'An open-source project that visualizes algorithms as they execute line-by-line.',
    link: 'https://algorithm-visualizer.org/',
  },
  {
    title: 'Apna College Notes',
    type: 'notes',
    topic: 'Revision',
    desc: 'Summarized PDF notes for quick revision before coding rounds or interviews.',
    link: 'https://www.apnacollege.in/notes',
  },
  {
    title: 'Take U Forward - DP',
    type: 'video',
    topic: 'Dynamic Prog',
    desc: 'A specialized deep dive into DP problems, from memoization to tabular solutions.',
    link: 'https://www.youtube.com/watch?v=tyB0ztf0DNY&list=PLgUwDviBIf0qUlt5H_kiKYaNSqJge11yG',
  },
];

@Component({
  selector: 'app-resource',
  standalone: true,
  imports: [RouterLink, FormsModule],
  templateUrl: './resource.component.html',
  styleUrl: './resource.component.css',
})
export class ResourceComponent {
  readonly all = RESOURCE_ITEMS;
  search = '';
  typeFilter: 'all' | ResourceItem['type'] = 'all';

  filtered(): ResourceItem[] {
    const q = this.search.trim().toLowerCase();
    return this.all.filter((item) => {
      const okType = this.typeFilter === 'all' || item.type === this.typeFilter;
      const okSearch =
        !q ||
        item.title.toLowerCase().includes(q) ||
        item.topic.toLowerCase().includes(q);
      return okType && okSearch;
    });
  }

  setType(t: typeof this.typeFilter): void {
    this.typeFilter = t;
  }
}
