import { Component, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';

@Component({ selector: 'app-resource', standalone: true, imports: [CommonModule, RouterLink], templateUrl: './resource.component.html', styleUrl: './resource.component.css' })
export class ResourceComponent implements OnInit {
  currentType = 'all';
  searchTerm = '';
  dsaData = [
    { 
      title: "Striver's A2Z Roadmap", 
      type: "video", 
      topic: "Full DSA", 
      desc: "The definitive video series for mastering algorithms from beginner to interview-ready.", 
      link: "https://www.youtube.com/playlist?list=PLgUwDviBIf0p-INQC6rMuzsSmdZ77EcrH" 
    },
    { 
      title: "VisuAlgo Visualizer", 
      type: "visual", 
      topic: "Concepts", 
      desc: "Interactive animations of data structures. Use this to see how nodes move in real-time.", 
      link: "https://visualgo.net/en" 
    },
    { 
      title: "Supreme DSA Notes", 
      type: "notes", 
      topic: "Handwritten", 
      desc: "Detailed Google Drive/GitHub notes covering core concepts with diagrams and code.", 
      link: "https://github.com/Ujjwal2327/DSA-SUPREME" 
    },
    { 
      title: "Algorithm Visualizer", 
      type: "visual", 
      topic: "Code-Sync", 
      desc: "An open-source project that visualizes algorithms as they execute line-by-line.", 
      link: "https://algorithm-visualizer.org/" 
    },
    { 
      title: "Apna College Notes", 
      type: "notes", 
      topic: "Revision", 
      desc: "Summarized PDF notes for quick revision before coding rounds or interviews.", 
      link: "https://www.apnacollege.in/notes" 
    },
    { 
      title: "Take U Forward - DP", 
      type: "video", 
      topic: "Dynamic Prog", 
      desc: "A specialized deep dive into DP problems, from memoization to tabular solutions.", 
      link: "https://www.youtube.com/watch?v=tyB0ztf0DNY&list=PLgUwDviBIf0qUlt5H_kiKYaNSqJge11yG" 
    }
  ];

  filteredData = [...this.dsaData];

  constructor() {}

  ngOnInit() {
    this.renderResources();
  }

  filterByType(type: string) {
    this.currentType = type;
    this.renderResources();
  }

  onSearch(event: any) {
    this.searchTerm = event.target.value.toLowerCase();
    this.renderResources();
  }

  renderResources() {
    this.filteredData = this.dsaData.filter(item => {
      const matchesType = this.currentType === 'all' || item.type === this.currentType;
      const matchesSearch = item.title.toLowerCase().includes(this.searchTerm) || 
                           item.topic.toLowerCase().includes(this.searchTerm);
      return matchesType && matchesSearch;
    });
  }
}
