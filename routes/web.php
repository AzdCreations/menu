<?php

use App\Menu;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Route;
//use app\Http\Controllers\UserController;
use App\Http\Controllers\UserController;
use App\Http\Controllers\MenuController;
/*
|--------------------------------------------------------------------------
| Web Routes
|--------------------------------------------------------------------------
|
| Here is where you can register web routes for your application. These
| routes are loaded by the RouteServiceProvider within a group which
| contains the "web" middleware group. Now create something great!
|
*/

Route::get('/', function () {
    $menus=Menu::where('status',1)->get();
    return view('welcome',['menus'=>$menus]);

});

Auth::routes();

Route::get('/home', 'HomeController@index')->name('home');

Route::prefix('admin')->name('admin.')->middleware( 'auth')->group(function () {
    Route::resource('users','UserController');
    Route::resource('menu','MenuController');
});
