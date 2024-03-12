<?php

namespace App\Http\Controllers;

use App\Menu;
use Illuminate\Http\Request;

class GeneralController extends Controller
{
    public function homepage()
    {
        $menus=Menu::where('status',1)->get();
        return view('home',['menus'=>$menus]);
    }
}
